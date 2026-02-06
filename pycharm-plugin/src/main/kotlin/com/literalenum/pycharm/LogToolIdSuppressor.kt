package com.literalenum.pycharm

import com.intellij.codeInspection.InspectionSuppressor
import com.intellij.codeInspection.SuppressQuickFix
import com.intellij.openapi.diagnostic.Logger
import com.intellij.psi.PsiElement

class LogToolIdSuppressor : InspectionSuppressor {
    companion object {
        private val LOG = Logger.getInstance(LogToolIdSuppressor::class.java)
    }

    override fun isSuppressedFor(element: PsiElement, toolId: String): Boolean {
        // Only log for Python files-ish to reduce spam
        val text = element.containingFile?.name ?: return false
        if (!text.endsWith(".py") && !text.endsWith(".pyi")) return false

        // This will show you the REAL inspection id producing the highlight.
        LOG.warn("LITERALENUM toolId=$toolId element=${element.javaClass.simpleName} text='${element.text.take(80)}'")
        return false
    }

    override fun getSuppressActions(element: PsiElement?, toolId: String): Array<SuppressQuickFix> {
        return SuppressQuickFix.EMPTY_ARRAY
    }
}
