import { IdpLifecycleState, IdpProtocol, OnboardingState } from "interfaces";

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
