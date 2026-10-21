export type ReviewReason =
  | "COVERAGE_MISMATCH"
  | "MISSING_INFORMATION"
  | "DUPLICATE_RECORD"
  | string;

export type Priority = "URGENT" | "HIGH" | "MEDIUM" | "LOW" | string;

export type SubmissionStatus =
  | "NEEDS_REVIEW"
  | "APPROVED"
  | "RETURNED"
  | string;

export type SortOrder =
  | "priority_desc"
  | "submitted_desc"
  | "submitted_asc"
  | "applicant_asc";

export interface Applicant {
  name: string | null;
  email: string | null;
}

export interface EmployerGroup {
  id: string;
  name: string;
}

export interface ReviewSignal {
  code: string;
  severity: string;
  field: string;
  message: string;
}

export interface Submission {
  id: string;
  applicant: Applicant;
  group: EmployerGroup;
  product: string;
  coverageAmountCents: number | null;
  submittedAt: string | null;
  effectiveDate: string | null;
  reviewReason: ReviewReason;
  priority: Priority;
  status: SubmissionStatus;
  employee?: {
    employeeId?: string | null;
    dateOfBirth?: string | null;
    phone?: string | null;
    address?: {
      line1?: string | null;
      line2?: string | null;
      city?: string | null;
      state?: string | null;
      postalCode?: string | null;
    } | null;
  } | null;
  employment?: {
    employmentStatus?: string | null;
    hireDate?: string | null;
    annualSalaryCents?: number | null;
    occupation?: string | null;
    hoursPerWeek?: number | null;
  } | null;
  election?: {
    planName?: string | null;
    requestedCoverageCents?: number | null;
    beneficiaryCount?: number | null;
    tobaccoUse?: boolean | null;
  } | null;
  existingCoverage?: {
    coverageAmountCents?: number | null;
    effectiveDate?: string | null;
    policyNumber?: string | null;
  } | null;
  reviewSignals?: ReviewSignal[] | null;
  decision?: {
    type?: string;
    note?: string | null;
    reviewedBy?: string;
  } | null;
  decidedAt?: string | null;
}

export interface SubmissionListResponse {
  items: Submission[];
  total: number;
}

export interface ApiErrorBody {
  error?: {
    code?: string;
    message?: string;
    details?: unknown;
  };
  submission?: Submission;
}

export class ApiError extends Error {
  status: number;
  code: string;
  submission?: Submission;

  constructor(
    message: string,
    status: number,
    code: string,
    submission?: Submission,
  ) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.submission = submission;
  }
}
