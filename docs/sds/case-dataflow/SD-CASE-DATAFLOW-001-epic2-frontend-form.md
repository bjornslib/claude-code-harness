---
title: "SD-CASE-DATAFLOW-001-E2: Frontend Form — shadcn Component Upgrade"
description: "Solution design for upgrading the New Case form to use proper shadcn/ui components with canonical type alignment"
version: "1.0.0"
last-updated: 2026-03-19
status: active
type: sd
grade: authoritative
prd_ref: PRD-CASE-DATAFLOW-001
---

# SD-CASE-DATAFLOW-001-E2: Frontend Form — shadcn Component Upgrade

## 1. Overview

This SD addresses Epic 2 of PRD-CASE-DATAFLOW-001: upgrading the `/checks-dashboard/new` form to use proper shadcn/ui components and canonical type definitions.

**Target**: `agencheck-support-frontend/`
**Worker Type**: `frontend-dev-expert`
**Depends On**: Epic 1 (TypeScript types from `lib/types/work-history.generated.ts`)

## 2. Current State

### 2.1 File Under Modification

`agencheck-support-frontend/app/checks-dashboard/new/page.tsx` (655 lines)

### 2.2 Current Components in Use

| Field | Component | Issue |
|-------|-----------|-------|
| Start/End Date | `<Input type="date">` | Browser-dependent, no format validation in Zod |
| Country | `<Input>` (free text) | Should be constrained to valid countries |
| Employment Type | `<Select>` with 3 options | Missing `contractor` (has `contract`), missing `casual` |
| Employment Arrangement | **Missing** | Backend model supports `direct`/`agency`/`subcontractor` |
| Agency Name | **Missing** | Needed when arrangement is agency/subcontractor |
| Phone Number | `<Input>` (free text) | No formatting or validation |

### 2.3 Current Zod Schema Issues

```typescript
// No date format validation:
startDate: z.string().min(1, 'Required'),
endDate: z.string().min(1, 'Required'),

// No format for phone:
contactPhoneNumber: z.string().optional(),

// No constraint for country:
employerCountry: z.string().min(1, 'Required'),
```

## 3. Solution Design

### 3.1 shadcn Components to Install/Use

```bash
npx shadcn@latest add calendar popover command
```

Components needed:
- `Calendar` + `Popover` = DatePicker pattern
- `Command` (Combobox) = Country autocomplete
- Existing `Select` = Employment Type (fix values)
- Existing `Select` = Employment Arrangement (new)
- Existing `Input` = Agency Name (conditional)

### 3.2 DatePicker Component

Create a reusable DatePicker component:

**File**: `agencheck-support-frontend/components/ui/date-picker.tsx`

```tsx
"use client";

import * as React from "react";
import { format } from "date-fns";
import { CalendarIcon } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

interface DatePickerProps {
  value?: string; // YYYY-MM-DD
  onChange: (date: string | undefined) => void;
  placeholder?: string;
  disabled?: boolean;
}

export function DatePicker({ value, onChange, placeholder = "Pick a date", disabled }: DatePickerProps) {
  const date = value ? new Date(value + "T00:00:00") : undefined;

  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          className={cn(
            "w-full justify-start text-left font-normal",
            !date && "text-muted-foreground"
          )}
          disabled={disabled}
        >
          <CalendarIcon className="mr-2 h-4 w-4" />
          {date ? format(date, "PPP") : <span>{placeholder}</span>}
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-auto p-0" align="start">
        <Calendar
          mode="single"
          selected={date}
          onSelect={(d) => onChange(d ? format(d, "yyyy-MM-dd") : undefined)}
          initialFocus
        />
      </PopoverContent>
    </Popover>
  );
}
```

### 3.3 Country Combobox

**File**: `agencheck-support-frontend/components/ui/country-combobox.tsx`

```tsx
"use client";

import * as React from "react";
import { Check, ChevronsUpDown } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Command, CommandEmpty, CommandGroup, CommandInput, CommandItem, CommandList } from "@/components/ui/command";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

// Top countries for AgenCheck usage, full list available
const COUNTRIES = [
  { value: "Australia", label: "Australia" },
  { value: "Singapore", label: "Singapore" },
  { value: "United States", label: "United States" },
  { value: "United Kingdom", label: "United Kingdom" },
  { value: "New Zealand", label: "New Zealand" },
  { value: "Canada", label: "Canada" },
  { value: "India", label: "India" },
  { value: "Philippines", label: "Philippines" },
  { value: "Malaysia", label: "Malaysia" },
  { value: "Indonesia", label: "Indonesia" },
  { value: "Japan", label: "Japan" },
  { value: "Hong Kong", label: "Hong Kong" },
  // ... extend with full ISO list as needed
];

interface CountryComboboxProps {
  value?: string;
  onChange: (country: string) => void;
  disabled?: boolean;
}

export function CountryCombobox({ value, onChange, disabled }: CountryComboboxProps) {
  const [open, setOpen] = React.useState(false);

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between"
          disabled={disabled}
        >
          {value || "Select country..."}
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[300px] p-0">
        <Command>
          <CommandInput placeholder="Search country..." />
          <CommandList>
            <CommandEmpty>No country found.</CommandEmpty>
            <CommandGroup>
              {COUNTRIES.map((country) => (
                <CommandItem
                  key={country.value}
                  value={country.value}
                  onSelect={(v) => {
                    onChange(v);
                    setOpen(false);
                  }}
                >
                  <Check className={cn("mr-2 h-4 w-4", value === country.value ? "opacity-100" : "opacity-0")} />
                  {country.label}
                </CommandItem>
              ))}
            </CommandGroup>
          </CommandList>
        </Command>
      </PopoverContent>
    </Popover>
  );
}
```

### 3.4 Updated Zod Schema

```typescript
import { EmploymentTypeEnum, EmploymentArrangementEnum } from "@/lib/types/work-history.generated";

const DATE_REGEX = /^\d{4}-\d{2}-\d{2}$/;

const schema = z.object({
  firstName: z.string().min(1, 'Required'),
  lastName: z.string().min(1, 'Required'),
  middleName: z.string().optional(),
  position: z.string().min(1, 'Required'),
  startDate: z.string().regex(DATE_REGEX, 'Must be YYYY-MM-DD format').min(1, 'Required'),
  endDate: z.string().regex(DATE_REGEX, 'Must be YYYY-MM-DD format').min(1, 'Required'),
  employmentType: z.enum(['full_time', 'part_time', 'contractor', 'casual']).optional(),
  employmentArrangement: z.enum(['direct', 'agency', 'subcontractor']).optional(),
  agencyName: z.string().optional(),
  taskId: z.string().optional(),
  employerName: z.string().min(1, 'Required'),
  employerWebsite: z.preprocess(
    (v) => (v === '' ? undefined : v),
    z.string().url('Invalid URL format').optional()
  ),
  employerCountry: z.string().min(1, 'Required'),
  employerCity: z.string().min(1, 'Required'),
  contactPersonName: z.string().optional(),
  contactPhoneNumber: z.string().optional(),
  contactEmail: z.string().email('Invalid email address').optional().or(z.literal('')),
  location: z.enum(['australia', 'singapore']),
  phoneType: z.string(),
  salaryAmount: z.string().optional().or(z.literal('')),
  supervisorName: z.string().optional().or(z.literal('')),
}).refine(
  (data) => !!data.contactPhoneNumber || !!data.employerWebsite,
  { message: 'Please provide either a Contact Phone Number or a Website', path: ['contactPhoneNumber'] }
).refine(
  (data) => {
    if (data.employmentArrangement === 'agency' || data.employmentArrangement === 'subcontractor') {
      return !!data.agencyName;
    }
    return true;
  },
  { message: 'Agency name is required for agency/subcontractor arrangements', path: ['agencyName'] }
);
```

### 3.5 Employment Type Select Update

Replace the current `<SelectContent>`:

```tsx
<SelectContent>
  <SelectItem value="full_time">Full-time</SelectItem>
  <SelectItem value="part_time">Part-time</SelectItem>
  <SelectItem value="contractor">Contractor</SelectItem>
  <SelectItem value="casual">Casual</SelectItem>
</SelectContent>
```

### 3.6 Employment Arrangement Select (New)

Add after Employment Type:

```tsx
<FormField
  control={form.control}
  name="employmentArrangement"
  render={({ field }) => (
    <FormItem>
      <FormLabel>Employment Arrangement</FormLabel>
      <Select onValueChange={field.onChange} value={field.value}>
        <FormControl>
          <SelectTrigger>
            <SelectValue placeholder="Select arrangement" />
          </SelectTrigger>
        </FormControl>
        <SelectContent>
          <SelectItem value="direct">Direct Employment</SelectItem>
          <SelectItem value="agency">Via Agency</SelectItem>
          <SelectItem value="subcontractor">Subcontractor</SelectItem>
        </SelectContent>
      </Select>
      <FormMessage />
    </FormItem>
  )}
/>
```

### 3.7 Conditional Agency Name

Add with AnimatePresence (same pattern as salary/supervisor):

```tsx
<AnimatePresence>
  {(form.watch('employmentArrangement') === 'agency' ||
    form.watch('employmentArrangement') === 'subcontractor') && (
    <motion.div
      initial={{ opacity: 0, height: 0 }}
      animate={{ opacity: 1, height: 'auto' }}
      exit={{ opacity: 0, height: 0 }}
      transition={{ duration: 0.2 }}
      className="overflow-hidden"
    >
      <FormField
        control={form.control}
        name="agencyName"
        render={({ field }) => (
          <FormItem>
            <FormLabel>Agency Name *</FormLabel>
            <FormControl>
              <Input {...field} placeholder="e.g., Robert Half, Hays" />
            </FormControl>
            <FormMessage />
          </FormItem>
        )}
      />
    </motion.div>
  )}
</AnimatePresence>
```

## 4. Files to Modify/Create

| File | Action |
|------|--------|
| `components/ui/date-picker.tsx` | **CREATE** — Reusable DatePicker |
| `components/ui/country-combobox.tsx` | **CREATE** — Reusable Country Combobox |
| `app/checks-dashboard/new/page.tsx` | **MODIFY** — Replace components, update schema |
| `lib/types/work-history.generated.ts` | **VERIFY** exists from Epic 1 |

### shadcn Dependencies to Install

```bash
cd agencheck-support-frontend
npx shadcn@latest add calendar popover command
npm install date-fns  # For date formatting
```

## 5. Test Strategy

1. Visual: All form fields render correctly with shadcn components
2. Functional: DatePicker produces YYYY-MM-DD strings
3. Validation: Zod rejects invalid dates, missing agency names
4. Type safety: Form compiles against generated TypeScript types
5. Regression: Submit flow still works end-to-end

## Implementation Status

| Task | Status | Date | Commit |
|------|--------|------|--------|
| Install shadcn dependencies | Remaining | - | - |
| Create DatePicker component | Remaining | - | - |
| Create CountryCombobox component | Remaining | - | - |
| Update form page | Remaining | - | - |
| Update Zod schema | Remaining | - | - |
