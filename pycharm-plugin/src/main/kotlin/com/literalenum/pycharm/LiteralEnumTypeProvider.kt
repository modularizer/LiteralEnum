package com.literalenum.pycharm

import com.intellij.openapi.diagnostic.Logger
import com.intellij.openapi.util.Ref
import com.intellij.psi.PsiElement
import com.jetbrains.python.psi.*
import com.jetbrains.python.psi.impl.PyBuiltinCache
import com.jetbrains.python.psi.types.*
import com.jetbrains.python.PyTokenTypes
import com.jetbrains.python.psi.PyBinaryExpression


/**
 * Type provider that makes LiteralEnum subclasses dual-natured:
 * - In annotation contexts: expands to Literal["GET"] | Literal["POST"] | ...
 * - In value positions: preserves normal class typing
 */
class LiteralEnumTypeProvider : PyTypeProviderBase() {

    companion object {
        private val LOG = Logger.getInstance(LiteralEnumTypeProvider::class.java)
        // Recursion guard for getCallableType
        private val inGetCallableType = ThreadLocal.withInitial { false }
    }

    /**
     * Rewrite the callable signature so that LiteralEnum-annotated parameters
     * appear as their Literal union type during call-site type checking.
     *
     * This is the CRITICAL hook — PyCharm uses the callable type (not getParameterType)
     * when checking arguments at call sites.
     */
    override fun getCallableType(callable: PyCallable, context: TypeEvalContext): PyType? {
        val func = callable as? PyFunction ?: return null

        // Skip dunders — they flood the log and aren't user-level annotations
        if (func.name?.startsWith("__") == true) return null

        // Recursion guard: context.getType(callable) calls back into getCallableType
        if (inGetCallableType.get()) return null
        inGetCallableType.set(true)
        try {
            return rewriteCallableType(func, context)
        } finally {
            inGetCallableType.set(false)
        }
    }

    private fun rewriteCallableType(func: PyFunction, context: TypeEvalContext): PyType? {
        val base = context.getType(func) as? PyCallableType ?: return null
        val baseParams = base.getParameters(context) ?: return null
        if (baseParams.isEmpty()) return null

        var changed = false

        val newParams = baseParams.map { p ->
            val psiParam = p.parameter as? PyNamedParameter
            val annoValue = psiParam?.annotation?.value as? PyExpression

            val rewritten: PyType? = if (annoValue != null) {
                resolveExpressionToLiteralUnion(annoValue, context)
            } else null

            if (rewritten != null) {
                changed = true
                LOG.warn("LITERALENUM getCallableType: rewriting ${func.name}.${psiParam?.name} to $rewritten")
            }

            object : PyCallableParameter by p {
                override fun getType(ctx: TypeEvalContext): PyType? {
                    return rewritten ?: p.getType(ctx)
                }
            }
        }

        if (!changed) return null

        val finalReturn = base.getReturnType(context)

        return object : PyCallableType by base {
            override fun getParameters(ctx: TypeEvalContext): List<PyCallableParameter> = newParams
            override fun getReturnType(ctx: TypeEvalContext): PyType? = finalReturn
        }
    }

    /**
     * Handle references like `HttpMethod` in annotation context.
     * Provides the type for tooltips and some resolution paths.
     */
    override fun getReferenceExpressionType(
        referenceExpression: PyReferenceExpression,
        context: TypeEvalContext
    ): PyType? {
        if (!isInAnnotationContext(referenceExpression)) return null

        // IMPORTANT: if we're inside a PEP-604 union (A | B), don't rewrite the operand.
        // Otherwise PyCharm can flag: "Type hint is invalid..."
        val parentBin = referenceExpression.parent as? PyBinaryExpression
        if (parentBin != null && parentBin.operator == PyTokenTypes.OR) {
            return null
        }

        val pyClass = resolveToLiteralEnumClass(referenceExpression, context) ?: return null
        return buildLiteralUnionType(pyClass, context)
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
        return Ref.create(literalType)
    }

    /**
     * Handle constructor calls like `HttpMethod("GET")`.
     */
    override fun getCallType(
        function: PyFunction,
        callSite: PyCallSiteExpression,
        context: TypeEvalContext
    ): Ref<PyType>? {
        val containingClass = function.containingClass ?: return null
        if (!isLiteralEnumClass(containingClass, context)) return null

        val unionType = buildLiteralUnionType(containingClass, context) ?: return null
        return Ref.create(unionType)
    }

    // ---- helpers ----

    internal fun resolveExpressionToLiteralUnion(expr: PyExpression, context: TypeEvalContext): PyType? {
        val e = (expr as? PyParenthesizedExpression)?.containedExpression ?: expr

        // Handle PEP-604 unions: A | B
        if (e is PyBinaryExpression && e.operator == PyTokenTypes.OR) {
            val parts = flattenOr(e)
            val partTypes = parts.mapNotNull { part ->
                // rewrite LiteralEnum class refs to literal unions, otherwise let PyCharm infer
                if (part is PyReferenceExpression) {
                    val resolved = part.reference.resolve() as? PyClass
                    if (resolved != null && isLiteralEnumClass(resolved, context)) {
                        buildLiteralUnionType(resolved, context)
                    } else {
                        context.getType(part)
                    }
                } else {
                    context.getType(part)
                }
            }
            return if (partTypes.isEmpty()) null else PyUnionType.union(partTypes)
        }

        // Simple reference: Colors
        if (e is PyReferenceExpression) {
            val resolved = e.reference.resolve() as? PyClass ?: return null
            if (!isLiteralEnumClass(resolved, context)) return null
            return buildLiteralUnionType(resolved, context)
        }

        return null
    }

    private fun flattenOr(expr: PyExpression): List<PyExpression> {
        val e = (expr as? PyParenthesizedExpression)?.containedExpression ?: expr
        val bin = e as? PyBinaryExpression ?: return listOf(e)
        if (bin.operator != PyTokenTypes.OR) return listOf(e)
        val left = bin.leftExpression ?: return listOf(e)
        val right = bin.rightExpression ?: return listOf(e)
        return flattenOr(left) + flattenOr(right)
    }


    private fun resolveToLiteralEnumClass(
        refExpr: PyReferenceExpression,
        context: TypeEvalContext
    ): PyClass? {
        val resolved = refExpr.reference.resolve() ?: return null
        val pyClass = resolved as? PyClass ?: return null
        if (!isLiteralEnumClass(pyClass, context)) return null
        return pyClass
    }

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

    private fun buildSingleLiteralType(
        member: LiteralMember,
        pyClass: PyClass,
        context: TypeEvalContext
    ): PyType? {
        if (member.typeTag == "none") {
            val builtinCache = PyBuiltinCache.getInstance(pyClass)
            return builtinCache.noneType
        }

        try {
            val literalType = PyLiteralType.getLiteralType(member.expression, context)
            if (literalType != null) return literalType
        } catch (_: Exception) {}

        try {
            val fromParam = PyLiteralType.fromLiteralParameter(member.expression, context)
            if (fromParam != null) return fromParam
        } catch (_: Exception) {}

        return null
    }
}
