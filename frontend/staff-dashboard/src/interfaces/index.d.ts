export interface ILegalAddress {
    first_name: string;
    last_name: string;
    country: string;
}

export interface IUser {
    id: number;
    username: string;
    email: string;
    legal_address?: ILegalAddress;
}

export interface IProduct {
    id: number;
    price: number;
    description: string;
    is_active: boolean;
    purchasable_object: object;
}

export interface IRedeemedOrder {
    id: number;
    created_on: Date;
    updated_on: Date;
    state: string;
    total_price_paid: number;
    reference_number: string;
    purchaser: number;
}

export interface IDiscount {
    id: number;
    discount_code: string;
    amount: string;
    discount_type: string;
    redemption_type: string;
    max_redemptions: number;
    payment_type: string;
    activation_date: Date;
    expiration_date: Date;
    is_bulk: boolean;
}

export interface IBulkDiscount {
    prefix: string;
    amount: string;
    discount_type: string;
    redemption_type: string;
    max_redemptions: number;
    payment_type: string;
    activates: Date;
    expires: Date;
}

export interface IDiscountRedemption {
    redemption_date: string;
    redeemed_by: Object;
    redeemed_discount: Object<IDiscount>;
    redeemed_order: IRedeemedOrder;
}

export interface IUserDiscount {
    id: number;
    discount: IDiscount;
    user: any;
}

export interface IDiscountProduct {
    id: number;
    discount: IDiscount;
    product: any;
}

export interface IDiscountProductRaw {
    id: number|null;
    discount_id: number|null;
    product_id: number|null;
}

export interface IDiscountTier {
    id: number;
    discount: number;
    current: boolean;
    income_threshold_usd: number;
    courseware_object: {
        title: string;
        readable_id: string;
        id: number;
        type: string;
    }
}

export interface ICourseware {
    id: number;
    title: string;
    readable_id: string;
    type:string;
}


export interface IFlexiblePriceIncome {
    income_usd: string;
    original_income: string;
    original_currency: string;
}


export interface IFlexiblePriceRequest {
    id: number;
    user: number;
    courseware: ICourseware;
    status: string;
    country_of_income: null;
    date_exchange_rate: Date;
    discount: IDiscount;
    date_documents_sent: Date;
    justification: string;
    country_of_residence: string;
    action: string;
    applicable_discounts: IDiscount[];
    income: IFlexiblePriceIncome
}

export interface IFlexiblePriceStatus {
    id: string;
    title: string;
}

export interface IFlexiblePriceRequestFilters {
    q: string;
    status: string;
    courseware: string;
}

export interface IFlexiblePriceStatusModalProps {
    record: IFlexiblePriceRequest;
    status: string;
    onClose: Function;
}

export interface IDiscountFilters {
    q: string;
    redemption_type: string;
    payment_type: string;
    is_redeemed: string;
}

export type OnboardingState =
    | "requested"
    | "org_created"
    | "idp_configured"
    | "idp_validated"
    | "contract_ready"
    | "live"
    | "blocked";

export type IdpLifecycleState = "draft" | "testing" | "active" | "disabled";

export type IdpProtocol = "saml" | "oidc";

export interface IOrganizationOnboarding {
    state: OnboardingState;
    state_changed_at: string;
    notes: string;
}

export interface IServiceProviderDetails {
    // entity_id and metadata_url are null for OIDC.
    entity_id: string | null;
    redirect_uri: string;
    metadata_url: string | null;
}

export interface IOrganizationIdentityProvider {
    id: number;
    alias: string;
    protocol: IdpProtocol;
    display_name: string;
    lifecycle_state: IdpLifecycleState;
    internal_id: string;
    metadata_source: string;
    metadata_artifact: Record<string, string> | null;
    metadata_fetched_at: string | null;
    created_on: string;
    updated_on: string;
    service_provider: IServiceProviderDetails;
}

export interface IProvisionedOrganization {
    id: number;
    name: string;
    org_key: string;
    org_key_prefix: string;
    description: string;
    slug: string;
    sso_organization_id: string | null;
    domains: string[] | null;
    redirect_url: string | null;
    onboarding: IOrganizationOnboarding | null;
    identity_providers: IOrganizationIdentityProvider[];
}

export interface IProvisioningEvent {
    id: number;
    action: string;
    identity_provider_alias: string;
    actor: { id: number; username: string; email: string } | null;
    data_before: Record<string, unknown> | null;
    data_after: Record<string, unknown> | null;
    created_on: string;
}

export type ContractMembershipType = "managed" | "code" | "auto";

export interface IContractProgram {
    readable_id: string;
    title: string;
    sort_order: number;
}

export interface IProvisionedContract {
    id: number;
    name: string;
    slug: string;
    organization: number;
    membership_type: ContractMembershipType;
    // Rich text, stored as HTML.
    description: string;
    welcome_message: string;
    contract_start: string | null;
    contract_end: string | null;
    active: boolean;
    max_learners: number | null;
    enrollment_fixed_price: string | null;
    programs: IContractProgram[];
}

export type ContractSetupStatus = "in_progress" | "complete" | "failed";

export type CourseRunCloneStatus = "pending" | "cloning" | "cloned" | "failed";

export interface IContractRunSetup {
    courseware_id: string;
    // null for a run created without an edX clone.
    clone_status: CourseRunCloneStatus | null;
    clone_attempts: number;
    clone_error: string;
}

export interface IContractSetupStatus {
    status: ContractSetupStatus;
    runs: IContractRunSetup[];
    enrollment_codes: { expected: number; existing: number };
}

export interface ICoursewareAddition {
    runs_added: number;
    courses_without_source_run: number;
    skipped_reason: string;
}

export interface IRemovedContractRun {
    courseware_id: string;
    unlinked: boolean;
}

export interface IContractEnrollmentCode {
    id: number;
    code: string;
    redemption_status: "unassigned" | "assigned" | "redeemed";
    assigned_to: string | null;
    assigned_on: string | null;
    assigned_name: string | null;
    redeemed_on: string | null;
    redeemed_by: string | null;
    last_sent: string | null;
    email_status: string | null;
    email_status_event_timestamp: string | null;
}

export interface IBulkAssignResult {
    assigned: IContractEnrollmentCode[];
    errors: { email: string; name: string; detail: string }[];
}

export interface IExpiredEnrollmentCode {
    code: string;
    deleted: boolean;
}

// DRF's PageNumberPagination envelope.
export interface IPage<T> {
    count: number;
    results: T[];
}
