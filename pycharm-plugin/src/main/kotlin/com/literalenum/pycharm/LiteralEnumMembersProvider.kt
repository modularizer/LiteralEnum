package com.literalenum.pycharm

import com.intellij.psi.PsiElement
import com.jetbrains.python.codeInsight.PyCustomMember
import com.jetbrains.python.psi.PyClass
import com.jetbrains.python.psi.resolve.PyResolveContext
import com.jetbrains.python.psi.types.PyClassMembersProviderBase
import com.jetbrains.python.psi.types.PyClassType
import com.jetbrains.python.psi.types.TypeEvalContext

/**
 * Provides synthetic members for LiteralEnum metaclass protocol methods.
 *
 * These methods are available on the class object itself (not instances):
 * mapping, unique_mapping, keys, values, items, validate, is_valid, etc.
 *
 * Registered via Pythonid.pyClassMembersProvider extension point.
 */
class LiteralEnumMembersProvider : PyClassMembersProviderBase() {

    companion object {
        /**
         * Synthetic members provided by the LiteralEnumMeta metaclass.
         */
        private val METACLASS_MEMBERS = listOf(
            PyCustomMember("mapping", "types.MappingProxyType", false),
            PyCustomMember("unique_mapping", "types.MappingProxyType", false),
            PyCustomMember("name_mapping", "types.MappingProxyType", false),
            PyCustomMember("names_mapping", "types.MappingProxyType", false),
            PyCustomMember("names_by_value", "types.MappingProxyType", false),
            PyCustomMember("keys", null as String?, false),
            PyCustomMember("values", null as String?, false),
            PyCustomMember("items", null as String?, false),
            PyCustomMember("validate", null as String?, false),
            PyCustomMember("is_valid", null as String?, false),
            PyCustomMember("names", null as String?, false),
            PyCustomMember("canonical_name", null as String?, false),
            PyCustomMember("matches_enum", null as String?, false),
            PyCustomMember("matches_literal", null as String?, false),
        )
    }

    override fun getMembers(
        clazz: PyClassType,
        location: PsiElement?,
        context: TypeEvalContext
    ): Collection<PyCustomMember> {
        // Only provide members for the class itself (definition), not instances
        if (!clazz.isDefinition) return emptyList()

        val pyClass = clazz.pyClass
        if (!isLiteralEnumClass(pyClass, context)) return emptyList()

        return METACLASS_MEMBERS
    }

    override fun resolveMember(
        type: PyClassType,
        name: String,
        location: PsiElement?,
        resolveContext: PyResolveContext
    ): PsiElement? {
        // Delegate to normal resolution through metaclass MRO
        return null
    }
}
