---
title: "Shadcn Patterns"
status: active
type: skill
last_verified: 2026-02-19
grade: authoritative
---

# shadcn/ui Patterns Reference

Best practices for implementing shadcn/ui components in Next.js 15 + React 19 applications.

## Core Principles

### 1. Copy-Not-Import

shadcn/ui components are copied into the project, not imported as dependencies. Customise directly in `src/components/ui/`.

```tsx
// ✅ Customise in your codebase
// src/components/ui/button.tsx
const buttonVariants = cva("...", {
  variants: {
    variant: {
      default: "bg-primary text-primary-foreground",
      // Add custom variant
      brand: "bg-blue-600 text-white hover:bg-blue-700",
    },
  },
});
```

### 2. Composition Over Props

Build complex components by composing primitives rather than adding props:

```tsx
// ❌ Avoid: Too many props
<Dialog
  title="Delete Item"
  description="Are you sure?"
  showCloseButton={true}
  size="lg"
/>

// ✅ Prefer: Composition
<Dialog>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Delete Item</DialogTitle>
      <DialogDescription>Are you sure?</DialogDescription>
    </DialogHeader>
    <DialogFooter>
      <Button variant="outline">Cancel</Button>
      <Button variant="destructive">Delete</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

### 3. className Customisation

Extend styles via `className` prop using Tailwind utilities:

```tsx
<Button variant="default" className="w-full sm:w-auto shadow-lg">
  Submit
</Button>
```

### 4. Accessibility First

All components must be accessible:

```tsx
// Icon buttons MUST have aria-label
<Button size="icon" aria-label="Delete item">
  <TrashIcon />
</Button>

// Forms MUST use FormControl for ARIA linkage
<FormField
  control={form.control}
  name="email"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Email</FormLabel>
      <FormControl>
        <Input {...field} />  {/* FormControl adds aria-describedby */}
      </FormControl>
      <FormMessage />
    </FormItem>
  )}
/>
```

---

## Component Quick Reference

| Component | Use Case | Key Features |
|-----------|----------|--------------|
| `Button` | Actions, triggers | Variants, sizes, loading state |
| `Input` | Text entry | Types, validation states |
| `Form` | Form validation | react-hook-form integration |
| `Dialog` | Modals | Portal, overlay, animations |
| `Sheet` | Side panels | Mobile-friendly drawers |
| `Table` | Data display | Semantic HTML, responsive |
| `Select` | Dropdowns | Searchable, keyboard nav |
| `Checkbox` | Boolean input | Indeterminate state |
| `Label` | Form labels | Auto-linked to inputs |
| `Textarea` | Multi-line input | Auto-resize support |
| `Tabs` | Navigation | Keyboard accessible |
| `Card` | Content containers | Header, content, footer |
| `Badge` | Status labels | Variants for states |
| `Skeleton` | Loading states | Placeholder UI |
| `Tooltip` | Hover hints | Delay, positioning |

---

## Form Integration

### Basic Form Pattern

```tsx
"use client";

import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import {
  Form, FormControl, FormDescription, FormField, FormItem, FormLabel, FormMessage,
} from "@/components/ui/form";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";

const schema = z.object({
  email: z.string().email(),
  name: z.string().min(2),
});

type FormValues = z.infer<typeof schema>;

export function MyFormClient() {
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", name: "" },
  });

  const onSubmit = form.handleSubmit(async (data) => {
    try {
      // API call or mutation
      toast.success("Saved successfully");
    } catch (error) {
      toast.error("Failed to save");
    }
  });

  return (
    <Form {...form}>
      <form onSubmit={onSubmit} className="space-y-4">
        <FormField
          control={form.control}
          name="email"
          render={({ field }) => (
            <FormItem>
              <FormLabel>Email</FormLabel>
              <FormControl>
                <Input type="email" placeholder="you@example.com" {...field} />
              </FormControl>
              <FormDescription>We'll never share your email.</FormDescription>
              <FormMessage />
            </FormItem>
          )}
        />

        <Button type="submit" loading={form.formState.isSubmitting}>
          Submit
        </Button>
      </form>
    </Form>
  );
}
```

### Common Field Patterns

**Number Input:**
```tsx
<FormField
  control={form.control}
  name="quantity"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Quantity</FormLabel>
      <FormControl>
        <Input
          type="number"
          inputMode="numeric"
          {...field}
          onChange={(e) => field.onChange(e.target.valueAsNumber)}
        />
      </FormControl>
      <FormMessage />
    </FormItem>
  )}
/>
```

**Select:**
```tsx
<FormField
  control={form.control}
  name="status"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Status</FormLabel>
      <Select onValueChange={field.onChange} defaultValue={field.value}>
        <FormControl>
          <SelectTrigger>
            <SelectValue placeholder="Select a status" />
          </SelectTrigger>
        </FormControl>
        <SelectContent>
          <SelectItem value="active">Active</SelectItem>
          <SelectItem value="inactive">Inactive</SelectItem>
        </SelectContent>
      </Select>
      <FormMessage />
    </FormItem>
  )}
/>
```

**Checkbox:**
```tsx
<FormField
  control={form.control}
  name="acceptTerms"
  render={({ field }) => (
    <FormItem className="flex flex-row items-start gap-3 space-y-0">
      <FormControl>
        <Checkbox checked={field.value} onCheckedChange={field.onChange} />
      </FormControl>
      <div className="space-y-1 leading-none">
        <FormLabel>Accept terms and conditions</FormLabel>
        <FormDescription>You agree to our Terms of Service.</FormDescription>
      </div>
    </FormItem>
  )}
/>
```

---

## Dialog Patterns

### Basic Dialog

```tsx
<Dialog>
  <DialogTrigger asChild>
    <Button variant="outline">Open Dialog</Button>
  </DialogTrigger>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Are you sure?</DialogTitle>
      <DialogDescription>This action cannot be undone.</DialogDescription>
    </DialogHeader>
    <DialogFooter>
      <Button variant="outline">Cancel</Button>
      <Button variant="destructive">Delete</Button>
    </DialogFooter>
  </DialogContent>
</Dialog>
```

### Controlled Dialog with Form

```tsx
"use client";

import { useState } from "react";

export function CreateDialogClient() {
  const [open, setOpen] = useState(false);
  const form = useForm({ /* ... */ });

  const createMutation = api.items.create.useMutation({
    onSuccess: () => {
      toast.success("Created successfully");
      form.reset();
      setOpen(false);  // Close dialog
    },
  });

  const onSubmit = form.handleSubmit((data) => {
    createMutation.mutate(data);
  });

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Create New</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create Item</DialogTitle>
          <DialogDescription>Add a new item to the system.</DialogDescription>
        </DialogHeader>

        <Form {...form}>
          <form onSubmit={onSubmit} className="space-y-4">
            {/* Form fields */}
            <DialogFooter>
              <Button
                type="button"
                variant="outline"
                onClick={() => setOpen(false)}
                disabled={createMutation.isPending}
              >
                Cancel
              </Button>
              <Button type="submit" loading={createMutation.isPending}>
                Create
              </Button>
            </DialogFooter>
          </form>
        </Form>
      </DialogContent>
    </Dialog>
  );
}
```

---

## Toast Notifications

Using Sonner for toast notifications:

```tsx
import { toast } from "sonner";

// Success
toast.success("Item created successfully");

// Error
toast.error("Failed to create item");

// With action
toast.success("Item deleted", {
  action: {
    label: "Undo",
    onClick: () => { /* Undo logic */ },
  },
});

// Promise toast (auto-updates)
toast.promise(mutation.mutateAsync(data), {
  loading: "Creating item...",
  success: "Item created successfully",
  error: "Failed to create item",
});
```

---

## Styling Patterns

### Responsive Design

```tsx
<div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
  {/* Mobile: 1 col, Tablet: 2 cols, Desktop: 3 cols */}
</div>

<Button className="w-full sm:w-auto">
  {/* Full width mobile, auto desktop */}
</Button>
```

### Conditional Styles with cn()

```tsx
import { cn } from "@/lib/utils";

<Button
  className={cn(
    "base-classes",
    isActive && "bg-blue-600",
    isDisabled && "opacity-50 cursor-not-allowed",
    variant === "large" && "text-lg px-6",
  )}
>
  Click me
</Button>
```

### Status Indicator Pattern

```tsx
const statusStyles = {
  active: "bg-green-500/10 text-green-600 dark:text-green-400",
  idle: "bg-muted text-muted-foreground",
  error: "bg-destructive/10 text-destructive",
  connecting: "bg-secondary/10 text-secondary animate-pulse",
} as const;

function StatusBadge({ status, label }: { status: keyof typeof statusStyles; label: string }) {
  return (
    <Badge className={statusStyles[status]}>
      <span className={cn(
        "w-2 h-2 rounded-full mr-2",
        status === "active" && "bg-green-500",
        status === "connecting" && "bg-secondary animate-pulse",
      )} />
      {label}
    </Badge>
  );
}
```

---

## Touch Target Sizes (WCAG 2.1 AAA)

Ensure minimum 44×44px touch targets on mobile:

```tsx
// Icon buttons - always 44×44px
<Button size="icon" className="h-11 w-11" aria-label="Add item">
  <PlusIcon />
</Button>

// Regular buttons - mobile-first sizing
<Button className="h-11 sm:h-9">
  {/* 44px mobile, 36px desktop */}
  Submit
</Button>

// List items as buttons
<button className="min-h-11 w-full text-left px-4 py-3">
  {/* 44px minimum height */}
  List item content
</button>
```

---

## Common Mistakes

### ❌ Missing aria-label on icon buttons

```tsx
// Bad
<Button size="icon"><TrashIcon /></Button>

// Good
<Button size="icon" aria-label="Delete item"><TrashIcon /></Button>
```

### ❌ Not using FormControl

```tsx
// Bad - missing ARIA linkage
<FormItem>
  <FormLabel>Email</FormLabel>
  <Input {...field} />  {/* No FormControl */}
  <FormMessage />
</FormItem>

// Good - proper ARIA linkage
<FormItem>
  <FormLabel>Email</FormLabel>
  <FormControl>
    <Input {...field} />
  </FormControl>
  <FormMessage />
</FormItem>
```

### ❌ Forgetting DialogTrigger asChild

```tsx
// Bad - creates nested button
<DialogTrigger><Button>Open</Button></DialogTrigger>

// Good - merges props into Button
<DialogTrigger asChild><Button>Open</Button></DialogTrigger>
```

### ❌ Hardcoded colours

```tsx
// Bad
<div className="bg-[#1E3A8A] text-white">

// Good
<div className="bg-primary text-primary-foreground">
```

---

## Loading States

```tsx
// Button with loading
<Button loading={isPending} loadingText="Saving...">
  Save Changes
</Button>

// Manual loading
<Button disabled={isPending}>
  {isPending && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
  Save Changes
</Button>

// Skeleton loading
if (isLoading) {
  return (
    <div className="space-y-3">
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
      <Skeleton className="h-10 w-full" />
    </div>
  );
}
```

---

## Installation

```bash
# Install shadcn CLI
pnpm dlx shadcn@latest init

# Add components
pnpm dlx shadcn@latest add button input form dialog table select checkbox textarea label
```
