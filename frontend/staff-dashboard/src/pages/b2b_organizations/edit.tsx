import { useForm, Edit } from "@refinedev/antd";
import { useGo } from "@refinedev/core";
import { Typography } from "antd";

import { OrganizationForm } from "components/b2b/organization_form";
import { B2B_ORGANIZATIONS } from "components/b2b/constants";
import { IProvisionedOrganization } from "interfaces";

type EditableField = "name" | "description" | "redirect_url" | "domains";
const EDITABLE_FIELDS: EditableField[] = ["name", "description", "redirect_url", "domains"];

// Send only what the operator changed. Keycloak can hold a null redirect URL,
// which the update endpoint rejects, and any domains sent are rewritten as
// verified, so resubmitting untouched fields has side effects.
const changedFields = (values: Partial<IProvisionedOrganization>, original?: IProvisionedOrganization) =>
    Object.fromEntries(
        EDITABLE_FIELDS.filter(
            (field) => JSON.stringify(values[field] ?? "") !== JSON.stringify(original?.[field] ?? ""),
        ).map((field) => [field, values[field] ?? ""]),
    );

export const OrganizationEdit = () => {
    const go = useGo();
    const showOrganization = () => go({ to: { resource: B2B_ORGANIZATIONS, action: "show", id: id as string } });
    const { formProps, saveButtonProps, query, id } = useForm<IProvisionedOrganization>({
        redirect: false,
        onMutationSuccess: showOrganization,
    });
    const organization = query?.data?.data;

    const onFinish = (values: Partial<IProvisionedOrganization>) => {
        const changes = changedFields(values, organization);
        if (Object.keys(changes).length === 0) {
            showOrganization();
            return;
        }
        return formProps.onFinish?.(changes);
    };

    return (
        <Edit
            title={`Edit ${organization?.name ?? "organization"}`}
            saveButtonProps={saveButtonProps}
            recordItemId={id}
        >
            <Typography.Paragraph>
                Org key: <Typography.Text code>{organization?.org_key}</Typography.Text>
            </Typography.Paragraph>
            <OrganizationForm formProps={{ ...formProps, onFinish }} creating={false} />
        </Edit>
    );
};
