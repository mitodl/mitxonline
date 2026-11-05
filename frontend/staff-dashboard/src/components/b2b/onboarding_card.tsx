import React from "react";
import { useApiUrl, useCustomMutation } from "@refinedev/core";
import { Button, Card, Descriptions, Form, Input, Select, Tag, Typography } from "antd";
import dayjs from "dayjs";

import { ONBOARDING_STATES, PROVISIONING_RESOURCE, onboardingState } from "./constants";
import { useRefreshOrganization } from "./use_refresh_organization";
import { IProvisionedOrganization, OnboardingState } from "interfaces";

interface IOnboardingForm {
    state: OnboardingState;
    notes: string;
}

// The onboarding state is descriptive: nothing gates on it. It records where
// the customer is so "what is left for this customer" has one answer.
export const OnboardingCard: React.FC<{ organization: IProvisionedOrganization }> = ({ organization }) => {
    const apiUrl = useApiUrl();
    const refresh = useRefreshOrganization(organization.org_key);
    const { mutate, isLoading } = useCustomMutation();
    const [form] = Form.useForm<IOnboardingForm>();
    const current = organization.onboarding;
    const state = onboardingState(current?.state);

    const onFinish = (values: IOnboardingForm) => {
        mutate(
            {
                url: `${apiUrl}/${PROVISIONING_RESOURCE}/${organization.org_key}/onboarding/`,
                method: "post",
                values,
                successNotification: { type: "success", message: "Onboarding state saved" },
            },
            { onSuccess: refresh },
        );
    };

    return (
        <Card title="Onboarding">
            <Descriptions column={1} size="small">
                <Descriptions.Item label="State">
                    {state ? <Tag color={state.color}>{state.label}</Tag> : <Tag>Not tracked</Tag>}
                </Descriptions.Item>
                {current && (
                    <Descriptions.Item label="Since">
                        {dayjs(current.state_changed_at).format("YYYY-MM-DD HH:mm")}
                    </Descriptions.Item>
                )}
                {current?.notes && (
                    <Descriptions.Item label="Notes">
                        <Typography.Text style={{ whiteSpace: "pre-wrap" }}>{current.notes}</Typography.Text>
                    </Descriptions.Item>
                )}
            </Descriptions>
            <Form
                form={form}
                layout="vertical"
                onFinish={onFinish}
                initialValues={{ state: current?.state, notes: current?.notes ?? "" }}
            >
                <Form.Item label="New state" name="state" rules={[{ required: true }]}>
                    <Select options={ONBOARDING_STATES.map(({ value, label }) => ({ value, label }))} />
                </Form.Item>
                <Form.Item label="Notes" name="notes" extra="For Blocked, say what the customer is waiting on.">
                    <Input.TextArea rows={3} />
                </Form.Item>
                <Button type="primary" htmlType="submit" loading={isLoading}>
                    Save onboarding state
                </Button>
            </Form>
        </Card>
    );
};
