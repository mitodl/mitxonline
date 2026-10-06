import { useForm, Create } from "@refinedev/antd";
import { useGo } from "@refinedev/core";

import { OrganizationForm } from "components/b2b/organization_form";
import { B2B_ORGANIZATIONS, PROVISIONING_RESOURCE } from "components/b2b/constants";
import { IProvisionedOrganization } from "interfaces";

export const OrganizationCreate = () => {
    const go = useGo();
    const { formProps, saveButtonProps } = useForm<IProvisionedOrganization>({
        resource: PROVISIONING_RESOURCE,
        action: "create",
        // The API looks organizations up by org_key, not the id the default
        // redirect would use.
        redirect: false,
        onMutationSuccess: ({ data }) => go({ to: { resource: B2B_ORGANIZATIONS, action: "show", id: data.org_key } }),
    });

    return (
        <Create title="Create organization" saveButtonProps={saveButtonProps}>
            <OrganizationForm formProps={formProps} creating />
        </Create>
    );
};
