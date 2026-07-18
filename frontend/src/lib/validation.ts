export interface ValidationError {
  field: string;
  message: string;
}

export interface ValidationRules {
  [key: string]: {
    required?: boolean;
    minLength?: number;
    maxLength?: number;
    pattern?: RegExp;
    custom?: (value: any) => string | null;
    message?: string;
  };
}

export function validateForm(
  data: Record<string, any>,
  rules: ValidationRules
): ValidationError[] {
  const errors: ValidationError[] = [];

  for (const [field, rule] of Object.entries(rules)) {
    const value = data[field];

    // Required validation
    if (rule.required && !value) {
      errors.push({
        field,
        message: rule.message || `${field} is required`
      });
      continue;
    }

    if (!value) continue;

    // Min length validation
    if (rule.minLength && value.length < rule.minLength) {
      errors.push({
        field,
        message: `${field} must be at least ${rule.minLength} characters`
      });
    }

    // Max length validation
    if (rule.maxLength && value.length > rule.maxLength) {
      errors.push({
        field,
        message: `${field} must not exceed ${rule.maxLength} characters`
      });
    }

    // Pattern validation
    if (rule.pattern && !rule.pattern.test(value)) {
      errors.push({
        field,
        message: rule.message || `${field} format is invalid`
      });
    }

    // Custom validation
    if (rule.custom) {
      const customError = rule.custom(value);
      if (customError) {
        errors.push({
          field,
          message: customError
        });
      }
    }
  }

  return errors;
}

export function validateEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  return emailRegex.test(email);
}

export function validatePhoneNumber(phone: string): boolean {
  const phoneRegex = /^[0-9]{10}$/;
  return phoneRegex.test(phone.replace(/\D/g, ""));
}

export function validateUrl(url: string): boolean {
  try {
    new URL(url);
    return true;
  } catch {
    return false;
  }
}

export function getErrorMessage(field: string, errors: ValidationError[]): string | null {
  const error = errors.find((e) => e.field === field);
  return error?.message || null;
}
