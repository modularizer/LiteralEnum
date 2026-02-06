package com.literalenum.pycharm

import com.intellij.psi.util.CachedValueProvider
import com.intellij.psi.util.CachedValuesManager
import com.intellij.psi.util.PsiModificationTracker
import com.intellij.psi.util.PsiTreeUtil
import com.jetbrains.python.PyTokenTypes
import com.jetbrains.python.psi.*
import com.jetbrains.python.psi.types.TypeEvalContext

/**
 * Fully-qualified names of the LiteralEnum base class.
 */
val LITERAL_ENUM_FQNS: Set<String> = setOf(
    "literalenum.LiteralEnum",
    "literalenum.literal_enum.LiteralEnum",
    "typing_literalenum.LiteralEnum"
)

/**
 * A single member extracted from a LiteralEnum class body.
 *
 * @param name     The attribute name (e.g. "GET")
 * @param expression The RHS PSI expression node
 * @param value    The literal value (String, Long, Boolean, or null for None)
 * @param typeTag  One of "str", "int", "bool", "bytes", "none"
 */
data class LiteralMember(
    val name: String,
    val expression: PyExpression,
    val value: Any?,
    val typeTag: String
)

/**
 * Check whether [pyClass] is a subclass of one of the LiteralEnum base FQNs.
 * Returns false if [pyClass] itself IS the base LiteralEnum.
 */
fun isLiteralEnumClass(pyClass: PyClass, context: TypeEvalContext): Boolean {
    val qName = pyClass.qualifiedName
    // The base class itself is not a LiteralEnum subclass
    if (qName != null && qName in LITERAL_ENUM_FQNS) return false

    // Fast path: check superclass expression names before expensive resolution
    val superExprNames = pyClass.superClassExpressions
        .filterIsInstance<PyReferenceExpression>()
        .mapNotNull { it.referencedName }
    if ("LiteralEnum" in superExprNames) {
        // Likely match — verify via resolution
        for (fqn in LITERAL_ENUM_FQNS) {
            if (pyClass.isSubclass(fqn, context)) return true
        }
    }

    // Check through full MRO for extend=True inheritance chains
    for (fqn in LITERAL_ENUM_FQNS) {
        if (pyClass.isSubclass(fqn, context)) return true
    }

    return false
}

/**
 * Extract all literal members from [pyClass] and its MRO ancestors.
 * Results are cached on the PSI element and invalidated on any PSI modification.
 *
 * Matches runtime behavior: skips names starting with `_` and descriptors.
 */
fun extractMembers(pyClass: PyClass, context: TypeEvalContext): List<LiteralMember> {
    return CachedValuesManager.getCachedValue(pyClass) {
        val members = doExtractMembers(pyClass, context)
        CachedValueProvider.Result.create(members, PsiModificationTracker.getInstance(pyClass.project))
    }
}

private fun doExtractMembers(pyClass: PyClass, context: TypeEvalContext): List<LiteralMember> {
    val result = mutableListOf<LiteralMember>()
    val seenNames = mutableSetOf<String>()

    // Walk MRO ancestors first (inherited members from extend=True chains)
    val ancestors = pyClass.getAncestorClasses(context)
    for (ancestor in ancestors) {
        val ancestorQName = ancestor.qualifiedName
        if (ancestorQName != null && ancestorQName in LITERAL_ENUM_FQNS) continue
        collectMembersFromClassBody(ancestor, result, seenNames)
    }

    // Then own class body
    collectMembersFromClassBody(pyClass, result, seenNames)

    return result
}

private fun collectMembersFromClassBody(
    pyClass: PyClass,
    result: MutableList<LiteralMember>,
    seenNames: MutableSet<String>
) {
    for (statement in pyClass.statementList.statements) {
        if (statement !is PyAssignmentStatement) continue
        val targets = statement.targets
        if (targets.size != 1) continue
        val target = targets[0] as? PyTargetExpression ?: continue
        val name = target.name ?: continue

        // Skip private/dunder names (runtime: name.startswith("_"))
        if (name.startsWith("_")) continue

        // Skip if already seen from an ancestor
        if (name in seenNames) continue

        val rhs = statement.assignedValue ?: continue

        // Skip descriptors: functions, classmethods, staticmethods, properties
        if (isDescriptorExpression(rhs)) continue

        val extracted = extractLiteralFromExpression(rhs) ?: continue
        val (value, typeTag) = extracted
        result.add(LiteralMember(name, rhs, value, typeTag))
        seenNames.add(name)
    }
}

/**
 * Check whether an expression represents a descriptor (function, classmethod, etc.)
 * that should be excluded from member collection.
 */
private fun isDescriptorExpression(expr: PyExpression): Boolean {
    // Lambda expressions
    if (expr is PyLambdaExpression) return true

    // Calls to classmethod(), staticmethod(), property(), etc.
    if (expr is PyCallExpression) {
        val callee = expr.callee as? PyReferenceExpression ?: return false
        val calleeName = callee.referencedName ?: return false
        return calleeName in setOf("classmethod", "staticmethod", "property")
    }

    return false
}

/**
 * Extract a literal value from a PSI expression.
 * Returns (value, typeTag) or null if not a supported literal.
 */
fun extractLiteralFromExpression(expr: PyExpression): Pair<Any?, String>? {
    when (expr) {
        is PyStringLiteralExpression -> {
            // Only plain strings, not bytes
            if (expr.isDocString) return null
            val value = expr.stringValue
            return Pair(value, "str")
        }
        is PyNumericLiteralExpression -> {
            if (expr.isIntegerLiteral) {
                val value = expr.bigIntegerValue?.toLong() ?: return null
                return Pair(value, "int")
            }
            // Floats are not valid Literal types
            return null
        }
        is PyBoolLiteralExpression -> {
            return Pair(expr.value, "bool")
        }
        is PyNoneLiteralExpression -> {
            return Pair(null, "none")
        }
        is PyReferenceExpression -> {
            // Handle bare True/False/None references
            val name = expr.referencedName
            return when (name) {
                "True" -> Pair(true, "bool")
                "False" -> Pair(false, "bool")
                "None" -> Pair(null, "none")
                else -> null
            }
        }
        is PyPrefixExpression -> {
            // Handle negative integers like -1
            if (expr.operator == PyTokenTypes.MINUS) {
                val operand = expr.operand as? PyNumericLiteralExpression ?: return null
                if (operand.isIntegerLiteral) {
                    val value = operand.bigIntegerValue?.toLong() ?: return null
                    return Pair(-value, "int")
                }
            }
            return null
        }
        else -> return null
    }
}

/**
 * Get a boolean keyword argument from the class definition.
 * e.g. `class Colors(LiteralEnum, call_to_validate=True):` → getClassKeywordBool(cls, "call_to_validate") = true
 * Returns null if the keyword is absent.
 */
fun getClassKeywordBool(pyClass: PyClass, keyword: String): Boolean? {
    val argList = pyClass.superClassExpressionList ?: return null
    for (arg in argList.arguments) {
        if (arg is PyKeywordArgument && arg.keyword == keyword) {
            val value = arg.valueExpression
            if (value is PyBoolLiteralExpression) return value.value
            return null
        }
    }
    return null
}

fun hasCallToValidate(pyClass: PyClass): Boolean = getClassKeywordBool(pyClass, "call_to_validate") == true
fun hasExtend(pyClass: PyClass): Boolean = getClassKeywordBool(pyClass, "extend") == true

/**
 * Resolve the effective `allow_aliases` setting for [pyClass].
 * Walks up the MRO: explicit `allow_aliases=False` on any ancestor wins.
 * Default is True (aliases allowed).
 */
fun effectiveAllowAliases(pyClass: PyClass, context: TypeEvalContext): Boolean {
    // Check own keyword first
    val own = getClassKeywordBool(pyClass, "allow_aliases")
    if (own != null) return own

    // Walk ancestors
    for (ancestor in pyClass.getAncestorClasses(context)) {
        val qName = ancestor.qualifiedName
        if (qName != null && qName in LITERAL_ENUM_FQNS) continue
        val ancestorVal = getClassKeywordBool(ancestor, "allow_aliases")
        if (ancestorVal != null) return ancestorVal
    }

    return true // default: aliases allowed
}

/**
 * Determine whether [element] is inside a type annotation context.
 *
 * Covers: parameter annotations, return type annotations, variable annotations,
 * TypeAlias RHS, and typing constructs like Optional[X], Union[X, ...].
 */
fun isInAnnotationContext(element: PyExpression): Boolean {
    // Direct parent is a PyAnnotation
    if (PsiTreeUtil.getParentOfType(element, PyAnnotation::class.java) != null) return true

    // Function return type annotation (-> X)
    val func = PsiTreeUtil.getParentOfType(element, PyFunction::class.java)
    if (func != null) {
        val annotation = func.annotation
        if (annotation != null && PsiTreeUtil.isAncestor(annotation, element, false)) return true
    }

    // Check if inside a subscription expression used as an annotation
    // e.g., Optional[HttpMethod], Union[HttpMethod, ...]
    val subscription = PsiTreeUtil.getParentOfType(element, PySubscriptionExpression::class.java)
    if (subscription != null) {
        return isInAnnotationContext(subscription)
    }

    return false
}

/**
 * Deduplicate members by (value, typeTag) for union construction.
 * Returns only unique members (first occurrence wins).
 */
fun deduplicateMembers(members: List<LiteralMember>): List<LiteralMember> {
    val seen = mutableSetOf<Pair<Any?, String>>()
    return members.filter { member ->
        val key = Pair(member.value, member.typeTag)
        seen.add(key) // returns true if newly added
    }
}
