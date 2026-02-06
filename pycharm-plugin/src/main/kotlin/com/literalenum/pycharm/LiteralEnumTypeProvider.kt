package com.literalenum.pycharm

import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.util.Ref
import com.intellij.psi.PsiElement
import com.jetbrains.python.psi.*
import com.jetbrains.python.psi.impl.PyBuiltinCache
import com.jetbrains.python.psi.types.*

/**
 * Type provider that makes LiteralEnum subclasses dual-natured:
 * - In annotation contexts: expands to Literal["GET"] | Literal["POST"] | ...
 * - In value positions: preserves normal class typing
 *
 * Registered via Pythonid.typeProvider extension point.
 */
class LiteralEnumTypeProvider : PyTypeProviderBase() {

    companion object {
        private val LOG = Logger.getInstance(LiteralEnumTypeProvider::class.java)
    }

    /**
     * Override the declared type of function parameters.
     * When a parameter is annotated with a LiteralEnum class, replace
     * the class type with the Literal union so that str arguments are accepted.
     */
    override fun getParameterType(
        param: PyNamedParameter,
        func: PyFunction,
        context: TypeEvalContext
    ): Ref<PyType>? {
        LOG.warn("LITERALENUM getParameterType CALLED: ${func.name}.${param.name}")
        val annotation = param.annotation
        LOG.warn("LITERALENUM getParameterType annotation=${annotation} annotationValue=${param.annotationValue}")
        if (annotation == null) return null
        val value = annotation.value
        LOG.warn("LITERALENUM getParameterType annotation.value=$value (${value?.javaClass?.simpleName})")
        val unionType = resolveAnnotationToLiteralUnion(annotation, context)
        LOG.warn("LITERALENUM getParameterType unionType=$unionType")
        return unionType?.let { Ref.create(it) }
    }

    /**
     * Override the return type of callables.
     * When a function's return annotation is a LiteralEnum class, replace
     * the class type with the Literal union.
     */
    override fun getReturnType(
        callable: PyCallable,
        context: TypeEvalContext
    ): Ref<PyType>? {
        val func = callable as? PyFunction ?: return null
        val annotation = func.annotation ?: return null
        val unionType = resolveAnnotationToLiteralUnion(annotation, context)
        if (unionType != null) {
            LOG.warn("LITERALENUM getReturnType: ${func.name} => $unionType")
        }
        return unionType?.let { Ref.create(it) }
    }

    /**
     * Handle references like `HttpMethod` in annotation context.
     * This provides the type for tooltips and some resolution paths.
     */
    override fun getReferenceExpressionType(
        referenceExpression: PyReferenceExpression,
        context: TypeEvalContext
    ): PyType? {
        if (!isInAnnotationContext(referenceExpression)) return null

        val pyClass = resolveToLiteralEnumClass(referenceExpression, context) ?: return null
        val result = buildLiteralUnionType(pyClass, context)
        if (result != null) {
            LOG.warn("LITERALENUM getReferenceExpressionType: ${pyClass.name} => $result")
        }
        return result
    }

    /**
     * Handle member access like `HttpMethod.GET`.
     * Returns the specific Literal type for that member.
     */
    override fun getReferenceType(
        target: PsiElement,
        context: TypeEvalContext,
        anchor: PsiElement?
    ): Ref<PyType>? {
        val targetExpr = target as? PyTargetExpression ?: return null
        val containingClass = targetExpr.containingClass ?: return null
        if (!isLiteralEnumClass(containingClass, context)) return null

        val memberName = targetExpr.name ?: return null
        val members = extractMembers(containingClass, context)
        val member = members.find { it.name == memberName } ?: return null

        val literalType = buildSingleLiteralType(member, containingClass, context) ?: return null
        LOG.warn("LITERALENUM getReferenceType: ${containingClass.name}.$memberName => $literalType")
        return Ref.create(literalType)
    }

    /**
     * Handle constructor calls like `HttpMethod("GET")`.
     * Returns the full literal union as the return type.
     */
    override fun getCallType(
        function: PyFunction,
        callSite: PyCallSiteExpression,
        context: TypeEvalContext
    ): Ref<PyType>? {
        val containingClass = function.containingClass ?: return null
        if (!isLiteralEnumClass(containingClass, context)) return null

        val unionType = buildLiteralUnionType(containingClass, context) ?: return null
        LOG.warn("LITERALENUM getCallType: ${containingClass.name} => $unionType")
        return Ref.create(unionType)
    }

    // ---- helpers ----

    /**
     * Given a PyAnnotation node, check if its value references a LiteralEnum class.
     * If so, return the Literal union type. Handles both bare references (`HttpMethod`)
     * and qualified references.
     */
    private fun resolveAnnotationToLiteralUnion(
        annotation: PyAnnotation,
        context: TypeEvalContext
    ): PyType? {
        val value = annotation.value ?: return null
        return resolveExpressionToLiteralUnion(value, context)
    }

    /**
     * Resolve an annotation expression to a Literal union if it references
     * a LiteralEnum class. Handles bare references, qualified references,
     * and subscription expressions like Optional[HttpMethod].
     */
    private fun resolveExpressionToLiteralUnion(
        expr: PyExpression,
        context: TypeEvalContext
    ): PyType? {
        when (expr) {
            is PyReferenceExpression -> {
                val pyClass = resolveToLiteralEnumClass(expr, context) ?: return null
                return buildLiteralUnionType(pyClass, context)
            }
            is PySubscriptionExpression -> {
                // Handle Optional[HttpMethod], list[HttpMethod], etc.
                // We don't transform the outer type, just ensure inner LiteralEnum
                // annotations get properly resolved by other mechanisms
                return null
            }
            else -> return null
        }
    }

    /**
     * Resolve a reference expression to a PyClass if it's a LiteralEnum subclass.
     */
    private fun resolveToLiteralEnumClass(
        refExpr: PyReferenceExpression,
        context: TypeEvalContext
    ): PyClass? {
        val resolved = refExpr.reference.resolve() ?: return null
        val pyClass = resolved as? PyClass ?: return null
        if (!isLiteralEnumClass(pyClass, context)) return null
        return pyClass
    }

    /**
     * Build a union type of all Literal types from the LiteralEnum's members.
     */
    private fun buildLiteralUnionType(pyClass: PyClass, context: TypeEvalContext): PyType? {
        val members = extractMembers(pyClass, context)
        if (members.isEmpty()) return null

        val uniqueMembers = deduplicateMembers(members)
        val literalTypes = uniqueMembers.mapNotNull { member ->
            buildSingleLiteralType(member, pyClass, context)
        }

        if (literalTypes.isEmpty()) return null
        if (literalTypes.size == 1) return literalTypes[0]
        return PyUnionType.union(literalTypes)
    }

    /**
     * Build a single PyLiteralType for a member.
     */
    private fun buildSingleLiteralType(
        member: LiteralMember,
        pyClass: PyClass,
        context: TypeEvalContext
    ): PyType? {
        if (member.typeTag == "none") {
            val builtinCache = PyBuiltinCache.getInstance(pyClass)
            return builtinCache.noneType
        }

        // Try getLiteralType first — the primary factory
        try {
            val literalType = PyLiteralType.getLiteralType(member.expression, context)
            if (literalType != null) return literalType
        } catch (_: Exception) {}

        // Try fromLiteralParameter as fallback
        try {
            val fromParam = PyLiteralType.fromLiteralParameter(member.expression, context)
            if (fromParam != null) return fromParam
        } catch (_: Exception) {}

        return null
    }
}
