import { HttpError } from "@refinedev/core";

import {
    ContractMembershipType,
    ContractSetupStatus,
    CourseRunCloneStatus,
    IdpLifecycleState,
    IdpProtocol,
    OnboardingState,
} from "interfaces";

// Mirrors b2b/constants.py. The API validates every value, so a drift here
// shows up as a 400 rather than as bad data.

// The resource's API path, and the identifier the app routes it by.
export const PROVISIONING_RESOURCE = "v0/b2b/provisioning/organizations";
export const B2B_ORGANIZATIONS = "b2b_organizations";

export const ONBOARDING_STATES: { value: OnboardingState; label: string; color: string }[] = [
    { value: "requested", label: "Requested", color: "default" },
    { value: "org_created", label: "Organization created", color: "blue" },
    { value: "idp_configured", label: "Identity provider configured", color: "geekblue" },
    { value: "idp_validated", label: "Identity provider validated", color: "cyan" },
    { value: "contract_ready", label: "Contract ready", color: "purple" },
    { value: "live", label: "Live", color: "green" },
    { value: "blocked", label: "Blocked", color: "red" },
];

export const IDP_STATES: { value: IdpLifecycleState; label: string; color: string }[] = [
    { value: "draft", label: "Draft", color: "default" },
    { value: "testing", label: "Testing", color: "gold" },
    { value: "active", label: "Active", color: "green" },
    { value: "disabled", label: "Disabled", color: "red" },
];

export const IDP_PROTOCOLS: { value: IdpProtocol; label: string }[] = [
    { value: "saml", label: "SAML" },
    { value: "oidc", label: "OIDC" },
];

// b2b.constants.IDP_ALLOWED_TRANSITIONS. There is no draft -> active edge:
// an IdP goes live only after somebody has logged in through it.
export const IDP_ALLOWED_TRANSITIONS: Record<IdpLifecycleState, IdpLifecycleState[]> = {
    draft: ["testing"],
    testing: ["draft", "active", "disabled"],
    active: ["testing", "disabled"],
    disabled: ["testing", "active"],
};

export const onboardingState = (value: string | undefined) =>
    ONBOARDING_STATES.find((state) => state.value === value);

export const idpState = (value: string | undefined) =>
    IDP_STATES.find((state) => state.value === value);

export const eventsResource = (orgKey: string) => `${PROVISIONING_RESOURCE}/${orgKey}/events`;

export const contractsUrl = (apiUrl: string, orgKey: string) => `${apiUrl}/${PROVISIONING_RESOURCE}/${orgKey}/contracts`;

export const organizationPath = (orgKey: string) => `/b2b_organizations/show/${orgKey}`;

export const contractPath = (orgKey: string, contractId: number | string) =>
    `${organizationPath(orgKey)}/contracts/${contractId}`;

// b2b.constants.CONTRACT_MEMBERSHIP_TYPE_CHOICES.
export const CONTRACT_MEMBERSHIP_TYPES: { value: ContractMembershipType; label: string }[] = [
    { value: "managed", label: "Managed" },
    { value: "code", label: "Enrollment Code" },
    { value: "auto", label: "Auto Enrollment" },
];

export const membershipType = (value: string | undefined) =>
    CONTRACT_MEMBERSHIP_TYPES.find((type) => type.value === value);

export const CONTRACT_SETUP_STATUSES: Record<ContractSetupStatus, { label: string; color: string }> = {
    in_progress: { label: "In progress", color: "gold" },
    complete: { label: "Complete", color: "green" },
    failed: { label: "Failed", color: "red" },
};

export const CLONE_STATUSES: Record<CourseRunCloneStatus, { label: string; color: string }> = {
    pending: { label: "Pending", color: "default" },
    cloning: { label: "Cloning", color: "gold" },
    cloned: { label: "Cloned", color: "green" },
    failed: { label: "Failed", color: "red" },
};

const errorMessages = (value: unknown) => (Array.isArray(value) ? value.join(" ") : JSON.stringify(value));

// The provisioning routes answer a refused request with {detail}, or with
// {errors} (main/exceptions.py wraps a 400's DRF errors), by field or as a
// list. Without this the notification only carries axios's "Request failed
// with status code 400". A 500 or 502 can carry an HTML page, which has no
// place in a notification, so a body that isn't an object is ignored.
const apiErrorDescription = (error?: HttpError): string | undefined => {
    const data = error?.response?.data;
    if (!data || typeof data !== "object") {
        return undefined;
    }
    if (typeof data.detail === "string") {
        return data.detail;
    }
    if (Array.isArray(data.errors)) {
        return errorMessages(data.errors);
    }
    if (data.errors && typeof data.errors === "object") {
        return Object.entries(data.errors as Record<string, unknown>)
            .map(([field, value]) =>
                field === "non_field_errors" ? errorMessages(value) : `${field}: ${errorMessages(value)}`,
            )
            .join(" ");
    }
    return JSON.stringify(data);
};

export const apiErrorNotification = (message: string) => (error?: HttpError) => ({
    type: "error" as const,
    message,
    description: apiErrorDescription(error),
});
