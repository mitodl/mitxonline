import { useInvalidate } from "@refinedev/core";

import { B2B_ORGANIZATIONS, eventsResource } from "./constants";

// Every provisioning write changes the organization, the list row and the
// change history, so refetch all three.
export const useRefreshOrganization = (orgKey: string) => {
    const invalidate = useInvalidate();

    return () => {
        invalidate({ resource: B2B_ORGANIZATIONS, invalidates: ["detail"], id: orgKey });
        invalidate({ resource: B2B_ORGANIZATIONS, invalidates: ["list"] });
        invalidate({ resource: eventsResource(orgKey), invalidates: ["list"] });
    };
};
