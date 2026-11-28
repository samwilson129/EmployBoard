export type AtsProvider =
  | "greenhouse"
  | "lever"
  | "ashby"
  | "smartrecruiters"
  | "recruitee"
  | "workable"
  | "personio"
  | "teamtailor";

export type EmploymentType =
  | "Full-time"
  | "Part-time"
  | "Contract"
  | "Internship"
  | "Temporary"
  | "Other";

export type WorkplaceType = "Remote" | "Hybrid" | "On-site" | "Unknown";

export type ExperienceLevel =
  | "Entry"
  | "Junior"
  | "Mid"
  | "Senior"
  | "Lead"
  | "Executive"
  | "Unknown";

export interface JobCompany {
  company_id: string;
  company_name: string;
  company_logo_url: string | null;
  company_website: string | null;
  careers_url: string | null;
}

export interface JobSourceRef {
  source_id: string;
  ats_provider: AtsProvider;
  external_job_id: string;
  original_job_url: string | null;
  fetched_at: string;
  last_verified_at: string | null;
}

export interface JobListItem {
  job_id: string;
  title: string;
  company: JobCompany;
  department: string | null;
  location: string | null;
  employment_type: EmploymentType | null;
  workplace_type: WorkplaceType | null;
  experience_level: ExperienceLevel | null;
  salary_min: number | null;
  salary_max: number | null;
  salary_currency: string | null;
  salary_interval: string | null;
  description_snippet: string | null;
  posted_at: string | null;
  first_seen_at: string;
  last_seen_at: string;
  updated_at: string;
  last_synced_at: string | null;
  application_url: string;
  ats_sources: AtsProvider[];
  primary_ats_provider: AtsProvider | null;
  is_active: boolean;
}

export interface JobDetail extends JobListItem {
  description: string | null;
  description_available: boolean;
  requirements: string | null;
  responsibilities: string | null;
  skills: string[] | null;
  expires_at: string | null;
  requisition_id: string | null;
  sources: JobSourceRef[];
  duplicate_of_job_id: string | null;
}

export interface JobListResponse {
  items: JobListItem[];
  total: number;
  page: number;
  limit: number;
  pages: number;
  sort: JobSort;
}

export interface FacetCount {
  value: string;
  label: string;
  count: number;
}

export interface FacetsResponse {
  locations: FacetCount[];
  departments: FacetCount[];
  employment_types: FacetCount[];
  workplace_types: FacetCount[];
  experience_levels: FacetCount[];
  ats_providers: FacetCount[];
  total_active_jobs: number;
}

export interface CompanyOut {
  company_id: string;
  company_name: string;
  company_slug: string;
  company_logo_url: string | null;
  company_website: string | null;
  careers_url: string | null;
  ats_provider: AtsProvider;
  board_identifier: string;
  is_active: boolean;
  active_job_count: number;
  total_job_count: number;
  last_successful_sync: string | null;
  verification_note: string | null;
}

export interface CompaniesResponse {
  items: CompanyOut[];
  total: number;
}

export interface SourceProviderOut {
  provider: AtsProvider;
  display_name: string;
  documentation_url: string;
  is_integrated: boolean;
  company_count: number;
  active_job_count: number;
  last_successful_sync: string | null;
  status: "operational" | "degraded" | "pending" | "not_configured";
}

export interface SourcesResponse {
  items: SourceProviderOut[];
  total_integrated: number;
  generated_at: string;
}

export interface StatsResponse {
  total_active_jobs: number;
  total_companies: number;
  active_companies: number;
  integrated_sources: number;
  total_job_sources: number;
  last_successful_sync: string | null;
  last_run_at: string | null;
  last_run_status: string | null;
  provider_job_counts: Record<string, number>;
  generated_at: string;
}

export type JobSort = "posted_desc" | "updated_desc" | "company_asc";
export type DatePosted = "all" | "24h" | "7d" | "30d";

export interface JobFilters {
  q: string;
  location: string;
  company: string;
  ats: string;
  employment_type: string;
  workplace_type: string;
  experience_level: string;
  department: string;
  date_posted: DatePosted;
  sort: JobSort;
  page: number;
  limit: number;
}

export const EMPTY_FILTERS: JobFilters = {
  q: "",
  location: "",
  company: "",
  ats: "",
  employment_type: "",
  workplace_type: "",
  experience_level: "",
  department: "",
  date_posted: "all",
  sort: "posted_desc",
  page: 1,
  limit: 20,
};
