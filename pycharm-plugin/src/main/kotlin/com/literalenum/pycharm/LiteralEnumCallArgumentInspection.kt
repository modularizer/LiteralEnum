package com.literalenum.pycharm

import com.intellij.codeInspection.LocalInspectionTool
import com.intellij.codeInspection.ProblemHighlightType
import com.intellij.codeInspection.ProblemsHolder
import com.intellij.psi.PsiElementVisitor
import com.jetbrains.python.inspections.PyInspectionVisitor
import com.jetbrains.python.psi.*
import com.jetbrains.python.psi.types.TypeEvalContext

/**
 * Replacement inspection for call-site argument checking when a parameter is annotated
 * with a LiteralEnum subclass.
 *
 * Why this exists:
 * PyCharm's built-in type checker reports "Expected HttpMethod, got str" because it does
 * NOT apply PyTypeProvider rewriting to the callable signature in this code path.
 *
 * This inspection checks membership directly:
 *   def handle(method: HttpMethod): ...
 *   handle("GET")  -> OK
 *   handle("git")  -> error (not in members)
 *
 * IMPORTANT: disable PyCharm's built-in "Type checker" inspection to avoid duplicate (wrong) errors.
 */
class LiteralEnumCallArgumentInspection : LocalInspectionTool() {

    override fun buildVisitor(holder: ProblemsHolder, isOnTheFly: Boolean): PsiElementVisitor {
        val ctx = TypeEvalContext.codeInsightFallback(holder.project)

        return object : PyInspectionVisitor(holder, ctx) {

            override fun visitPyCallExpression(node: PyCallExpression) {
                super.visitPyCallExpression(node)

                val callee = node.callee ?: return
                val resolved = (callee as? PyReferenceExpression)?.reference?.resolve() ?: return

                val func = resolved as? PyFunction ?: return
                val params = func.parameterList.parameters
                val args = node.arguments

                if (params.isEmpty() || args.isEmpty()) return

                // MVP: positional args only (covers your handle("GET") case)
                val n = minOf(params.size, args.size)
                for (i in 0 until n) {
                    val param = params[i] as? PyNamedParameter ?: continue
                    val anno = param.annotation ?: continue
                    val annoExpr = anno.value as? PyReferenceExpression ?: continue

                    val annoResolved = annoExpr.reference.resolve() as? PyClass ?: continue
                    if (!isLiteralEnumClass(annoResolved, myTypeEvalContext)) continue

                    // We now know: this parameter is annotated with a LiteralEnum subclass.
                    // Enforce: string literal args must be one of the members.
                    val argExpr = args[i] as? PyExpression ?: continue

                    val literal = extractLiteralFromExpression(argExpr) ?: continue
                    val literalValue = literal.first
                    val literalTag = literal.second

                    // Only enforce for str/int/bool/none literals; ignore other values.
                    val members = extractMembers(annoResolved, myTypeEvalContext)
                    val ok = members.any { m -> m.value == literalValue && m.typeTag == literalTag }

                    if (!ok) {
                        val expected = members.joinToString(", ") { m ->
                            when (m.typeTag) {
                                "str" -> "\"${m.value}\""
                                else -> m.value.toString()
                            }
                        }

                        holder.registerProblem(
                            argExpr,
                            "Value ${renderLiteral(literalValue, literalTag)} is not a member of ${annoResolved.name}; expected one of: $expected",
                            ProblemHighlightType.GENERIC_ERROR_OR_WARNING
                        )
                    }
                }
            }
        }
    }

    private fun renderLiteral(value: Any?, tag: String): String {
        return when (tag) {
            "str" -> "\"$value\""
            "none" -> "None"
            else -> value.toString()
        }
    }
}
