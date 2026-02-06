package com.literalenum.pycharm

import com.intellij.codeInspection.InspectionSuppressor
import com.intellij.codeInspection.SuppressQuickFix
import com.intellij.openapi.diagnostic.Logger
import com.intellij.psi.PsiElement
import com.intellij.psi.util.PsiTreeUtil
import com.jetbrains.python.psi.*
import com.jetbrains.python.psi.types.TypeEvalContext

/**
 * Suppresses type-mismatch false positives when a literal value is passed
 * to a parameter annotated with a LiteralEnum subclass.
 *
 * Covers both PyTypeChecker and PyArgumentList inspections, since the
 * "Expected type 'HttpMethod', got 'str'" warning can originate from either.
 */
class LiteralEnumTypeCheckerSuppressor : InspectionSuppressor {

    companion object {
        private val LOG = Logger.getInstance(LiteralEnumTypeCheckerSuppressor::class.java)

        // Inspection suppressIds (confirmed from LogToolIdSuppressor output)
        private val SUPPRESSED_TOOL_IDS = setOf(
            "PyTypeChecker",
            "PyArgumentList"
        )
    }

    override fun isSuppressedFor(element: PsiElement, toolId: String): Boolean {
        if (toolId !in SUPPRESSED_TOOL_IDS) return false

        // PyCharm often asks suppression on a LEAF token inside "GET",
        // not on the PyExpression. Climb to the nearest expression first.
        val argExpr = PsiTreeUtil.getParentOfType(element, PyExpression::class.java, false) ?: return false

        // Now climb to the call this argument belongs to.
        val argList = PsiTreeUtil.getParentOfType(argExpr, PyArgumentList::class.java, false) ?: return false
        val callExpr = argList.parent as? PyCallExpression ?: return false

        val callee = callExpr.callee as? PyReferenceExpression ?: return false
        val resolved = callee.reference.resolve() as? PyFunction ?: return false

        // Positional argument index
        val args = callExpr.arguments
        val index = args.indexOfFirst { it == argExpr || PsiTreeUtil.isAncestor(it, argExpr, false) }
        if (index < 0) return false

        val params = resolved.parameterList.parameters

        // Account for self/cls: argument index 0 maps to param index 1 for methods
        val paramOffset = if (params.isNotEmpty()) {
            val first = params[0] as? PyNamedParameter
            if (first != null && first.isSelf) 1 else 0
        } else 0

        val param = params.getOrNull(index + paramOffset) as? PyNamedParameter ?: return false

        val anno = param.annotation ?: return false
        val annoExpr = anno.value as? PyReferenceExpression ?: return false
        val annoClass = annoExpr.reference.resolve() as? PyClass ?: return false

        val ctx = TypeEvalContext.codeInsightFallback(element.project)
        if (!isLiteralEnumClass(annoClass, ctx)) return false

        // Only suppress if the argument is a literal AND is a valid member.
        val (value, tag) = extractLiteralFromExpression(argExpr) ?: return false

        val members = extractMembers(annoClass, ctx)
        val isMember = members.any { it.value == value && it.typeTag == tag }

        if (isMember) {
            LOG.warn("LITERALENUM suppressor[$toolId]: OK for ${annoClass.name}.$value")
        }

        return isMember
    }

    override fun getSuppressActions(element: PsiElement?, toolId: String): Array<SuppressQuickFix> {
        return SuppressQuickFix.EMPTY_ARRAY
    }
}
