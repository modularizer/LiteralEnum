package com.literalenum.pycharm

import com.intellij.codeInspection.LocalInspectionTool
import com.intellij.codeInspection.ProblemHighlightType
import com.intellij.codeInspection.ProblemsHolder
import com.intellij.psi.PsiElementVisitor
import com.jetbrains.python.inspections.PyInspectionVisitor
import com.jetbrains.python.psi.*
import com.jetbrains.python.psi.types.TypeEvalContext
import com.intellij.psi.util.PsiTreeUtil


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
                val calleeName = (callee as? PyReferenceExpression)?.referencedName

                // isinstance/issubclass are not supported for LiteralEnum
                if (calleeName == "isinstance" || calleeName == "issubclass") {
                    checkIsinstanceCall(node, calleeName)
                    return
                }

                val resolved = (callee as? PyReferenceExpression)?.reference?.resolve() ?: return

                // Check direct class calls: Colors("BLUE")
                if (resolved is PyClass && isLiteralEnumClass(resolved, myTypeEvalContext)) {
                    checkConstructorCall(node, resolved)
                    return
                }

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

            private fun checkConstructorCall(node: PyCallExpression, pyClass: PyClass) {
                if (!hasCallToValidate(pyClass)) {
                    holder.registerProblem(
                        node,
                        "'${pyClass.name}' is not callable; use ${pyClass.name}.validate(x) or pass call_to_validate=True",
                        ProblemHighlightType.GENERIC_ERROR_OR_WARNING
                    )
                    return
                }

                // call_to_validate=True: check that the argument is a valid member
                val args = node.arguments
                if (args.isEmpty()) return
                val argExpr = args[0] as? PyExpression ?: return
                val literal = extractLiteralFromExpression(argExpr) ?: return
                val members = extractMembers(pyClass, myTypeEvalContext)
                val ok = members.any { it.value == literal.first && it.typeTag == literal.second }
                if (!ok) {
                    val expected = members.joinToString(", ") { m ->
                        when (m.typeTag) {
                            "str" -> "\"${m.value}\""
                            else -> m.value.toString()
                        }
                    }
                    holder.registerProblem(
                        argExpr,
                        "Value ${renderLiteral(literal.first, literal.second)} is not a member of ${pyClass.name}; expected one of: $expected",
                        ProblemHighlightType.GENERIC_ERROR_OR_WARNING
                    )
                }
            }

            override fun visitPyClass(node: PyClass) {
                super.visitPyClass(node)
                if (!isLiteralEnumClass(node, myTypeEvalContext)) return
                checkMissingExtend(node)
                checkDuplicateAliases(node)
            }

            private fun checkMissingExtend(node: PyClass) {
                if (hasExtend(node)) return

                // Check if any parent LiteralEnum has members
                for (ancestor in node.getAncestorClasses(myTypeEvalContext)) {
                    val qName = ancestor.qualifiedName
                    if (qName != null && qName in LITERAL_ENUM_FQNS) continue
                    if (!isLiteralEnumClass(ancestor, myTypeEvalContext)) continue

                    val parentMembers = extractMembers(ancestor, myTypeEvalContext)
                    if (parentMembers.isNotEmpty()) {
                        // Find the superclass expression to highlight
                        val superExpr = node.superClassExpressions
                            .filterIsInstance<PyReferenceExpression>()
                            .find { it.referencedName == ancestor.name }

                        holder.registerProblem(
                            superExpr ?: node.nameIdentifier ?: node,
                            "Cannot subclass '${ancestor.name}' without extend=True; it already has members",
                            ProblemHighlightType.GENERIC_ERROR_OR_WARNING
                        )
                        return
                    }
                }
            }

            private fun checkDuplicateAliases(node: PyClass) {
    if (effectiveAllowAliases(node, myTypeEvalContext)) return

    val seen = mutableMapOf<Pair<Any?, String>, String>() // (value, tag) -> first name

    // 1) Seed with inherited members (so child aliases are caught)
    val allMembers = extractMembers(node, myTypeEvalContext)
    for (m in allMembers) {
        val isFromThisClass = PsiTreeUtil.isAncestor(node, m.expression, /* strict = */ false)
        if (isFromThisClass) continue
        val key = Pair(m.value, m.typeTag)
        seen.putIfAbsent(key, m.name) // first occurrence wins (e.g. RED before CRIMSON)
    }

    // 2) Check duplicates in *this* class against inherited + previous in this class
    for (statement in node.statementList.statements) {
        if (statement !is PyAssignmentStatement) continue
        val targets = statement.targets
        if (targets.size != 1) continue
        val target = targets[0] as? PyTargetExpression ?: continue
        val name = target.name ?: continue
        if (name.startsWith("_")) continue

        val rhs = statement.assignedValue ?: continue
        if (isDescriptorExpression(rhs)) continue

        val extracted = extractLiteralFromExpression(rhs) ?: continue
        val key = Pair(extracted.first, extracted.second)

        val existing = seen[key]
        if (existing != null) {
            holder.registerProblem(
                target,
                "Duplicate value ${renderLiteral(extracted.first, extracted.second)}: '$name' is an alias for '$existing' (allow_aliases=False)",
                ProblemHighlightType.GENERIC_ERROR_OR_WARNING
            )
        } else {
            seen[key] = name
        }
    }
}


            private fun checkIsinstanceCall(node: PyCallExpression, funcName: String) {
                val args = node.arguments
                if (args.size < 2) return

                val classArg = args[1] as? PyReferenceExpression ?: return
                val resolved = classArg.reference.resolve() as? PyClass ?: return

                if (!isLiteralEnumClass(resolved, myTypeEvalContext)) return

                holder.registerProblem(
                    node,
                    "$funcName() is not supported for LiteralEnum subclass '${resolved.name}'; LiteralEnum values are plain literals, not class instances",
                    ProblemHighlightType.GENERIC_ERROR_OR_WARNING
                )
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
