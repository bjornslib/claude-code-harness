# Example: Researching React Hook Patterns

## Scenario

Need to implement a custom hook for managing form state with validation in a Next.js app.

## Research Query

```python
Task(
    subagent_type="general-purpose",
    model="haiku",
    description="Research React form hooks patterns",
    prompt="""
    Research Query: What's the current best practice for custom form hooks with validation in React 19?

    Context: Building a Next.js 15 app with server actions. Need client-side validation before submission.

    Steps:
    1. Use mcp__context7__resolve-library-id for "react"
    2. Use mcp__context7__query-docs for "custom hooks form validation useActionState"
    3. Use mcp__perplexity-ask__perplexity_ask to validate:
       - Is useActionState the right choice for client+server validation?
       - Should I use react-hook-form or build custom?
       - Any gotchas with React 19 form handling?

    Return Format:
    ## Current Best Practice
    [What React 19 docs recommend for forms]

    ## Code Example
    ```tsx
    [Working custom form hook example]
    ```

    ## Gotchas
    [React 19 specific notes, common mistakes]

    ## Recommendation
    [Whether to use library or custom, and why]
    """
)
```

## Expected Response Summary

```markdown
## Current Best Practice
React 19 introduces `useActionState` for form handling with server actions.
For client-side validation, combine with `useOptimistic` for instant feedback.

## Code Example
```tsx
function useValidatedForm<T>(action: (state: T, formData: FormData) => Promise<T>, initialState: T) {
  const [state, formAction, isPending] = useActionState(action, initialState);
  const [errors, setErrors] = useState<Record<string, string>>({});

  const validate = (formData: FormData): boolean => {
    // Client-side validation
    const newErrors: Record<string, string> = {};
    // ... validation logic
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (formData: FormData) => {
    if (validate(formData)) {
      formAction(formData);
    }
  };

  return { state, handleSubmit, isPending, errors };
}
```

## Gotchas
- `useActionState` replaces `useFormState` (renamed in React 19)
- Server actions run after client validation passes
- useOptimistic should wrap display values, not form inputs

## Recommendation
For simple forms: Custom hook with useActionState (shown above)
For complex forms: react-hook-form + zod, integrates well with server actions
```

## After Implementation

Store the pattern in Hindsight:

```python
mcp__hindsight__retain(
    content="React 19 form pattern: useActionState for server actions + custom validation hook. useOptimistic for instant feedback on display values. react-hook-form for complex forms.",
    context="patterns"
)
```
