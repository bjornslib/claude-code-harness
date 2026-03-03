# PRD-PIPELINE-ENGINE-001 Epic 3: Condition Expression Language
# Blind acceptance rubric — independent tests for E3 implementation
# Generated from SD-PIPELINE-ENGINE-001-epic3-5-conditions-loops.md (Epic 3 sections only)
# Guardian: Do NOT share this file with orchestrators or workers.
#
# This file provides GRANULAR scenario coverage for each of the 16 E3 acceptance criteria.
# The existing scenarios-epic3-5.feature provides high-level feature coverage;
# this file adds detailed scoring criteria per AC.

@feature-F9 @weight-0.15
Feature: F9 — Condition Expression Lexer and Parser (Detailed)

  # --- LEXER SCENARIOS ---

  Scenario: S9.1a — Lexer produces correct token types for all categories
    Given the following condition expression: "$retry_count < 3 && $status = \"success\""
    When ConditionLexer().tokenize(expr) is called
    Then it produces a list of Token objects ending with EOF
    And $retry_count produces a VARIABLE token with path ("retry_count",)
    And < produces a LT token
    And 3 produces an INTEGER token with value 3
    And && produces an AND token
    And $status produces a VARIABLE token with path ("status",)
    And = produces an EQ token
    And "success" produces a STRING token with value "success"

    # Confidence scoring guide:
    # 1.0 — All token types correctly identified. Token dataclass is frozen with type,
    #        value, and position fields. Position tracks byte offset. Whitespace consumed.
    # 0.7 — Tokens correct but missing position tracking or Token is not frozen.
    # 0.3 — Only basic tokens work; fails on multi-char operators (&&, ||, <=, >=).
    # 0.0 — No lexer; uses regex splitting or str.split().

    # Evidence to check:
    # - cobuilder/engine/conditions/lexer.py exists with ConditionLexer class
    # - Token dataclass in ast.py with type: TokenType, value: ..., position: int
    # - TokenType enum has all 18 members

    # Red flags:
    # - Using str.split() or simple regex instead of character-by-character scanning
    # - Token class is not frozen (mutable tokens)
    # - No position tracking in Token

  Scenario: S9.1b — Lexer handles all 18 token types including BARE_WORD (AMD-5)
    Given expressions with INTEGER, FLOAT, STRING, BOOLEAN, VARIABLE, BARE_WORD tokens
    And expressions with EQ, NEQ, LT, GT, LTE, GTE operator tokens
    And expressions with AND, OR, NOT logical tokens
    And expressions with LPAREN, RPAREN grouping tokens
    When ConditionLexer().tokenize() is called on each
    Then each token type is correctly emitted
    And BARE_WORD tokens produce a deprecation warning (AMD-5)
    And "true" and "false" (case-insensitive) produce BOOLEAN tokens
    And single and double quoted strings both produce STRING tokens
    And negative numbers produce INTEGER/FLOAT tokens with negative values

    # Confidence scoring guide:
    # 1.0 — Full 18-type TokenType enum. BARE_WORD emits DeprecationWarning.
    #        Both quote styles work. Case-insensitive boolean literals. Negative numbers.
    # 0.5 — Most tokens work but BARE_WORD missing, or no deprecation warning.
    # 0.0 — TokenType has fewer than 15 members or uses generic string types.

    # Evidence to check:
    # - TokenType enum member count (should be 18)
    # - Test file: tests/engine/conditions/test_lexer.py — look for BARE_WORD tests
    # - Python warnings module usage for deprecation warning

    # Red flags:
    # - No BARE_WORD token type (AMD-5 violation)
    # - Boolean parsing is case-sensitive
    # - Missing FLOAT token type

  Scenario: S9.1c — Lexer error handling with position info
    Given invalid input like bare & (not &&), bare | (not ||), or unclosed quotes
    When ConditionLexer().tokenize() is called
    Then it raises ConditionLexError with position and source snippet
    And the error message includes the character position of the invalid token
    And the error message includes a human-readable description

    # Confidence scoring guide:
    # 1.0 — ConditionLexError raised with position: int, source: str, message: str.
    #        Bare & and | correctly rejected. Unclosed quotes caught.
    # 0.5 — Error raised but lacks position or source context.
    # 0.0 — Generic ValueError/RuntimeError instead of ConditionLexError.

    # Evidence to check:
    # - ConditionLexError class in ast.py or errors.py
    # - Error.__init__ signature includes position and source parameters
    # - Test cases for bare &, bare |, unclosed quotes

  # --- PARSER SCENARIOS ---

  Scenario: S9.2a — Parser produces correct AST for simple comparison (E3-AC1, E3-AC2)
    Given expression "$retry_count < 3"
    When parse_condition(expr) is called
    Then it returns a ComparisonNode
    And ComparisonNode.operator is TokenType.LT
    And ComparisonNode.left is VariableNode(path=("retry_count",))
    And ComparisonNode.right is LiteralNode(value=3)

    # Confidence scoring guide:
    # 1.0 — ComparisonNode with correct field types. VariableNode path is a tuple.
    #        LiteralNode value is typed (int 3, not string "3").
    # 0.5 — AST produced but variable path is a string instead of tuple.
    # 0.0 — No parser; eval() or string matching used.

    # Evidence to check:
    # - cobuilder/engine/conditions/parser.py — ConditionParser class
    # - cobuilder/engine/conditions/ast.py — ComparisonNode, VariableNode, LiteralNode
    # - Test: "$retry_count < 3" produces exact AST shape

  Scenario: S9.2b — Parser handles AND/OR with correct precedence (E3-AC1, E3-AC5)
    Given expression "$retry_count < 3 && $status = success"
    When parse_condition(expr) is called
    Then it returns BinaryOpNode(AND, ComparisonNode(...), ComparisonNode(...))
    And given "$a < 5 || $b = done && $c > 1"
    Then AND binds tighter than OR (precedence: NOT > AND > OR)
    And the AST is BinaryOpNode(OR, ComparisonNode($a<5), BinaryOpNode(AND, ...))

    # Confidence scoring guide:
    # 1.0 — Correct precedence: NOT > AND > OR. Recursive-descent with separate
    #        _parse_or(), _parse_and(), _parse_not() methods.
    # 0.5 — Parsing works but all operators are left-associative (flat, no precedence).
    # 0.0 — No recursive descent; flat if/elif matching.

    # Evidence to check:
    # - parser.py has _parse_or, _parse_and, _parse_not methods
    # - Test: "$a || $b && $c" produces OR(a, AND(b, c)), not AND(OR(a, b), c)

    # Red flags:
    # - Single parse method without precedence levels
    # - AND and OR at same precedence
    # - Missing NOT support

  Scenario: S9.2c — Parser handles NOT, parentheses, and nesting (E3-AC4, E3-AC12)
    Given expression "!($status = failed)"
    When parse_condition(expr) is called
    Then it returns NotNode(ComparisonNode(EQ, VariableNode("status"), LiteralNode("failed")))
    And given "(($a < 3) && ($b > 1))"
    Then nested parentheses parse correctly respecting grouping
    And given "($a || $b) && $c"
    Then parentheses override default OR < AND precedence

    # Confidence scoring guide:
    # 1.0 — NotNode, parenthesized expressions, nested parentheses all work.
    #        Parser has _parse_atom() method that handles LPAREN/RPAREN.
    # 0.5 — NOT works but parentheses fail on nesting depth > 1.
    # 0.0 — No NOT support or parentheses not handled.

    # Evidence to check:
    # - NotNode class in ast.py
    # - _parse_atom handles LPAREN token by recursing into _parse_or

  Scenario: S9.2d — Parser error messages with position info (E3-AC9)
    Given malformed expression "$retry_count >> 5" (invalid operator)
    When parse_condition(expr) is called
    Then it raises ConditionParseError
    And the error includes the failing token's position
    And the error includes a snippet of the source expression
    And the error includes a human-readable message like "Expected operator, got '>'"

    # Confidence scoring guide:
    # 1.0 — ConditionParseError with position, source snippet, and descriptive message.
    #        Error raised at exact token location. Includes "valid operators" hint.
    # 0.5 — Error raised but lacks position or source context.
    # 0.0 — Generic exception or no error (silent failure).

    # Evidence to check:
    # - ConditionParseError class with position, token, source fields
    # - Test file has malformed expression tests


@feature-F10 @weight-0.10
Feature: F10 — Condition Evaluator (Detailed)

  Scenario: S10.1a — Basic evaluation against PipelineContext (E3-AC1, E3-AC2)
    Given a PipelineContext with {"$retry_count": 2, "$status": "success"}
    When evaluate_condition("$retry_count < 3 && $status = success", context) is called
    Then it returns True
    And evaluate_condition("$retry_count >= 3", context) returns False
    And evaluate_condition("$retry_count < 3", context) returns True
    And evaluate_condition("$status != success", context) returns False

    # Confidence scoring guide:
    # 1.0 — Evaluator walks AST correctly. Variables resolved from context with $ prefix
    #        (AMD-4). All 6 comparison operators work. AND/OR logical operators work.
    # 0.5 — Basic comparisons work but missing some operators or wrong $ handling.
    # 0.0 — Evaluator uses string matching or Python eval().

    # Evidence to check:
    # - cobuilder/engine/conditions/evaluator.py — ConditionEvaluator class
    # - evaluate() method walks ASTNode tree
    # - Variables looked up WITH $ prefix in context (AMD-4)

    # Red flags:
    # - Using Python eval() or exec()
    # - Variables looked up WITHOUT $ prefix (violates AMD-4)

  Scenario: S10.1b — Dotted variable resolution (E3-AC3)
    Given a PipelineContext with {"$node_visits": {"impl_auth": 3}}
    When evaluate_condition("$node_visits.impl_auth > 2", context) is called
    Then it returns True (resolved via nested dict lookup)
    And evaluate_condition("$node_visits.impl_auth = 3", context) returns True
    And evaluate_condition("$node_visits.missing_node > 0", context) handles missing var

    # Confidence scoring guide:
    # 1.0 — Dotted paths resolve through nested dicts. path=("node_visits", "impl_auth")
    #        resolves to context["$node_visits"]["impl_auth"]. Missing nested key handled.
    # 0.5 — Dotted paths work for one level but fail for deeper nesting.
    # 0.0 — No dotted path support; only flat key lookup.

    # Evidence to check:
    # - evaluator.py _resolve_variable() handles multi-segment paths
    # - VariableNode.path is a tuple that gets traversed

  Scenario: S10.1c — Missing variable handling (E3-AC6, E3-AC7)
    Given a PipelineContext with {"$status": "success"} (no $missing_var)
    When evaluate_condition("$missing_var = foo", context, missing_var_default=False) is called
    Then it returns False (default value used, no exception)
    And when evaluate_condition("$missing_var = foo", context) with no default
    Then it raises MissingVariableError
    And MissingVariableError includes the variable path in the message
    And MissingVariableError includes available context keys for debugging

    # Confidence scoring guide:
    # 1.0 — missing_var_default=False returns False silently. No default raises
    #        MissingVariableError with path and available keys. Uses _SENTINEL pattern.
    # 0.5 — Missing variable raises but wrong exception type, or default doesn't work.
    # 0.0 — Missing variable causes KeyError or crashes.

    # Evidence to check:
    # - MissingVariableError class with path: tuple[str, ...] and context_keys: list[str]
    # - evaluate() signature has missing_var_default parameter with _SENTINEL default

  Scenario: S10.1d — Type coercion at comparison boundaries (E3-AC8)
    Given expressions comparing mixed types
    When evaluate_condition("$count > \"3\"", context_with_count_5) is called
    Then string "3" is coerced to int 3 for comparison, returns True
    And evaluate_condition("$count > abc", context) raises ConditionTypeError
    And int vs float comparisons work (int coerced to float)
    And bool comparisons with < or > raise ConditionTypeError

    # Confidence scoring guide:
    # 1.0 — Type coercion table from SD §4.6 fully implemented. ConditionTypeError on
    #        incompatible types. str→int coercion for numeric strings. int→float promotion.
    #        Bool only allows = and != (not < > <= >=).
    # 0.5 — Basic coercion works but edge cases fail (bool + ordering, non-numeric string).
    # 0.0 — No type coercion; strict type matching fails on mixed comparisons.

    # Evidence to check:
    # - _coerce_for_comparison() method in evaluator.py
    # - ConditionTypeError class
    # - Test matrix covering str/int, str/float, int/float, bool pairings

    # Red flags:
    # - No type coercion logic
    # - Using Python's implicit type comparison (breaks on str vs int ordering)

  Scenario: S10.1e — Short-circuit evaluation (E3-AC5)
    Given a PipelineContext where $a exists but $b does NOT exist
    When evaluate_condition("$a = 1 || $b = 2", context) is called with $a=1
    Then it returns True WITHOUT evaluating $b (short-circuit OR)
    And no MissingVariableError is raised for $b
    And evaluate_condition("$a = 0 && $b = 2", context) with $a=0
    Then it returns False WITHOUT evaluating $b (short-circuit AND)
    And no MissingVariableError is raised for $b

    # Confidence scoring guide:
    # 1.0 — AND short-circuits on False (left=False → skip right). OR short-circuits
    #        on True (left=True → skip right). Variables on skipped branch not resolved.
    # 0.5 — Short-circuit works for one operator but not both.
    # 0.0 — Both branches always evaluated (no short-circuit).

    # Evidence to check:
    # - BinaryOpNode evaluation in evaluator.py checks left result before evaluating right
    # - Test that confirms MissingVariableError NOT raised on skipped branch

  Scenario: S10.2a — validate_condition_syntax() API (E3-AC9, E3-AC10)
    Given valid expression "$x < 5"
    When validate_condition_syntax("$x < 5") is called
    Then it returns an empty list (no errors)
    And given invalid expression "$x >> 5"
    When validate_condition_syntax("$x >> 5") is called
    Then it returns a non-empty list of error strings
    And the function NEVER raises — always returns errors as strings
    And error strings include position information

    # Confidence scoring guide:
    # 1.0 — Public API function in conditions/__init__.py. Returns list[str] (empty=valid).
    #        Never raises. Error strings include position. Used by Rule 7.
    # 0.5 — Function exists but raises instead of returning error list.
    # 0.0 — No syntax validation function; Rule 7 does its own parsing.

    # Evidence to check:
    # - conditions/__init__.py exports validate_condition_syntax
    # - Function signature returns list[str]
    # - try/except around parse_condition, catching ConditionParseError

  Scenario: S10.2b — AMD-5 bare word backward compatibility (E3-AC11)
    Given expression "$status = success" (bare word "success" without quotes)
    When parse_condition(expr) is called
    Then it succeeds (not a parse error)
    And the lexer emits a BARE_WORD token for "success"
    And a deprecation warning is logged (Python warnings module)
    And the parser treats BARE_WORD as LiteralNode(value="success")
    And evaluate_condition("$status = success", context_with_status_success) returns True

    # Confidence scoring guide:
    # 1.0 — Bare words accepted as implicit string literals. DeprecationWarning emitted.
    #        Parser produces LiteralNode. Evaluator compares correctly against context.
    #        validate_condition_syntax() returns warnings (not errors) for bare words.
    # 0.5 — Bare words accepted but no deprecation warning.
    # 0.0 — Bare words cause parse error (breaks backward compatibility).

    # Evidence to check:
    # - BARE_WORD in TokenType enum
    # - warnings.warn() call in lexer for bare words
    # - validate_condition_syntax returns warning-level messages for bare words


@feature-F11 @weight-0.05
Feature: F11 — Condition Error Hierarchy (Detailed)

  Scenario: S11.1a — Full error class hierarchy
    Given the conditions error/exception module
    Then ConditionError exists as the base exception
    And ConditionLexError inherits from ConditionError
    And ConditionParseError inherits from ConditionError
    And ConditionEvalError inherits from ConditionError
    And MissingVariableError inherits from ConditionEvalError
    And ConditionTypeError inherits from ConditionEvalError

    # Confidence scoring guide:
    # 1.0 — Full hierarchy matching SD §4.9. All 6 classes present.
    #        ConditionError is the catch-all for callers.
    # 0.5 — Hierarchy exists but MissingVariableError or ConditionTypeError
    #        inherits from wrong parent.
    # 0.0 — Using generic exceptions (ValueError, RuntimeError).

    # Evidence to check:
    # - All 6 classes in conditions/ast.py or conditions/errors.py
    # - issubclass(MissingVariableError, ConditionEvalError) is True
    # - issubclass(ConditionLexError, ConditionError) is True

  Scenario: S11.1b — Error context fields
    Given each error class
    Then ConditionLexError has position: int, source: str, message: str
    And ConditionParseError has token: Token, source: str, message: str
    And MissingVariableError has path: tuple[str, ...], context_keys: list[str]
    And all errors produce a useful str() representation

    # Confidence scoring guide:
    # 1.0 — All context fields present per SD spec. str() output includes position
    #        and human-readable description.
    # 0.5 — Some context fields missing (e.g., no position in LexError).
    # 0.0 — Bare Exception subclasses with no custom fields.

    # Evidence to check:
    # - __init__ signatures match SD §4.9 spec
    # - __str__ or __repr__ produces useful output


@feature-F10-integration @weight-0.05
Feature: F10-Integration — Edge Selector and Validator Integration

  Scenario: S10.3a — EdgeSelector Step 1 calls evaluate_condition (E3-AC14, E3-AC16)
    Given a graph with two outgoing edges from a node:
      | edge   | condition                    |
      | edge_a | $retry_count < 3             |
      | edge_b | $retry_count >= 3            |
    And PipelineContext has $retry_count = 1
    When select_next_edge() is called (edge_selector.py)
    Then it evaluates edge_a's condition first (returns True) and selects edge_a
    And if $retry_count = 5, it selects edge_b
    And if condition evaluation raises ConditionEvalError, it is caught and edge is skipped
    And the evaluator is called with missing_var_default=False

    # Confidence scoring guide:
    # 1.0 — edge_selector.py imports evaluate_condition from conditions package.
    #        Step 1 iterates outgoing edges with .condition attribute. First True wins.
    #        ConditionEvalError caught, logged at WARNING, edge skipped. Falls through
    #        to Steps 2-5 if no condition matches.
    # 0.5 — Integration exists but errors not caught (crashes on eval error).
    # 0.0 — edge_selector.py does not call evaluate_condition at all.

    # Evidence to check:
    # - edge_selector.py: "from cobuilder.engine.conditions import evaluate_condition"
    # - For loop over edges with condition attribute
    # - try/except block around evaluate_condition call
    # - Fallback to Steps 2-5 when no condition matches

    # Red flags:
    # - Condition evaluation done inline (not calling conditions package)
    # - No error handling around evaluate_condition

  Scenario: S10.3b — Validator Rule 7 calls validate_condition_syntax (E3-AC15)
    Given a graph with edges that have condition attributes
    When Validator runs Rule 7 (ConditionSyntaxValid)
    Then it calls validate_condition_syntax() for each edge with a condition
    And valid conditions produce no violations
    And invalid conditions produce WARNING or ERROR-level violations
    And bare words produce WARNING-level violations (AMD-5)

    # Confidence scoring guide:
    # 1.0 — Rule 7 in validation/rules.py imports validate_condition_syntax from
    #        conditions package. Iterates all edges. Invalid = ERROR. Bare word = WARNING.
    # 0.5 — Rule 7 exists but does its own parsing instead of calling conditions package.
    # 0.0 — Rule 7 is a stub or does not validate condition syntax.

    # Evidence to check:
    # - validation/rules.py imports from cobuilder.engine.conditions
    # - ConditionSyntaxValid rule iterates graph.edges
    # - Violation severity: ERROR for invalid, WARNING for bare words

  Scenario: S10.3c — Performance: parse_condition under 1ms (E3-AC13)
    Given a 200-character condition expression with multiple AND/OR/NOT operators
    When parse_condition(expr) is called 1000 times
    Then average execution time is under 1ms per call
    And no I/O or network calls occur during parsing

    # Confidence scoring guide:
    # 1.0 — Performance test exists in test suite. Benchmark confirms <1ms.
    #        Parser is pure computation (no I/O).
    # 0.5 — No explicit performance test but parser design is clearly O(n).
    # 0.0 — Parser makes I/O calls or has O(n²) complexity.

    # Evidence to check:
    # - Test file has a benchmark/performance test
    # - Parser and lexer have no I/O operations
