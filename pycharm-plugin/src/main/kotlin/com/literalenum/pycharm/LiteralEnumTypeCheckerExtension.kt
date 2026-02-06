package com.literalenum.pycharm

import com.intellij.openapi.diagnostic.Logger
import com.jetbrains.python.psi.types.*
import java.util.Optional

/**
 * Type checker extension that makes literal values compatible with LiteralEnum
 * class annotations.
 *
 * When a parameter is annotated as `HttpMethod` (a LiteralEnum subclass),
 * this extension tells PyCharm that `str` values (and specifically `Literal["GET"]`)
 * are compatible with `HttpMethod`, preventing false "Expected type 'HttpMethod',
 * got 'str'" errors.
 *
 * Registered via Pythonid.typeCheckerExtension extension point.
 */
class LiteralEnumTypeCheckerExtension : PyTypeCheckerExtension {

    companion object {
        private val LOG = Logger.getInstance(LiteralEnumTypeCheckerExtension::class.java)

        private val LITERAL_BUILTIN_QNAMES = mapOf(
            "str" to "builtins.str",
            "int" to "builtins.int",
            "bool" to "builtins.bool",
            "bytes" to "builtins.bytes"
        )
    }

    override fun match(
        expected: PyType?,
        actual: PyType?,
        context: TypeEvalContext,
        substitutions: PyTypeChecker.GenericSubstitutions
    ): Optional<Boolean> {
        if (expected == null || actual == null) return Optional.empty()

        // Get the expected class — must be a LiteralEnum subclass
        val expectedClass = when (expected) {
            is PyClassType -> expected.pyClass
            else -> return Optional.empty()
        }

        if (!isLiteralEnumClass(expectedClass, context)) return Optional.empty()

        val members = extractMembers(expectedClass, context)
        if (members.isEmpty()) return Optional.empty()
        val memberTypeTags = members.map { it.typeTag }.toSet()

        // Case 1: actual is a PyLiteralType (e.g., Literal["GET"])
        // Check if this specific literal value is a member of the enum
        if (actual is PyLiteralType) {
            val expression = actual.expression
            val extracted = extractLiteralFromExpression(expression)
            if (extracted != null) {
                val (value, typeTag) = extracted
                val uniqueMembers = deduplicateMembers(members)
                val isMember = uniqueMembers.any { it.value == value && it.typeTag == typeTag }
                LOG.warn("LITERALENUM typeChecker: Literal match ${expectedClass.name} vs Literal[$value] => $isMember")
                return Optional.of(isMember)
            }
            // If we can't extract the literal, check by base type
            val literalClass = actual.pyClass
            val literalQName = literalClass.qualifiedName
            val isBaseTypeMatch = LITERAL_BUILTIN_QNAMES.any { (tag, qname) ->
                literalQName == qname && tag in memberTypeTags
            }
            if (isBaseTypeMatch) {
                LOG.warn("LITERALENUM typeChecker: Literal base type match ${expectedClass.name} => true")
                return Optional.of(true)
            }
        }

        // Case 2: actual is a plain class type (e.g., str, int)
        // Accept if the LiteralEnum has members of that type
        if (actual is PyClassType) {
            val actualQName = actual.pyClass.qualifiedName
            val isCompatible = LITERAL_BUILTIN_QNAMES.any { (tag, qname) ->
                actualQName == qname && tag in memberTypeTags
            }
            if (isCompatible) {
                LOG.warn("LITERALENUM typeChecker: class match ${expectedClass.name} vs $actualQName => true")
                return Optional.of(true)
            }
        }

        // Case 3: actual is a union type — defer to PyCharm's default union handling
        // which will call match() for each member of the union

        return Optional.empty()
    }
}
