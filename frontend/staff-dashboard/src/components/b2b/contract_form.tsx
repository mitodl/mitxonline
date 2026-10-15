import React from "react";
import { DatePicker, Form, FormInstance, Input, InputNumber, Select, Switch } from "antd";
import dayjs, { Dayjs } from "dayjs";

import { CONTRACT_MEMBERSHIP_TYPES } from "./constants";
import { ContractMembershipType, IProvisionedContract } from "interfaces";

export interface IContractForm {
    name: string;
    membership_type: ContractMembershipType;
    description: string;
    welcome_message: string;
    contract_start: Dayjs | null;
    contract_end: Dayjs | null;
    active: boolean;
    max_learners: number | null;
    enrollment_fixed_price: string | null;
}

const DATE_FORMAT = "YYYY-MM-DD";

export const contractToForm = (contract: IProvisionedContract): IContractForm => ({
    ...contract,
    contract_start: contract.contract_start ? dayjs(contract.contract_start) : null,
    contract_end: contract.contract_end ? dayjs(contract.contract_end) : null,
});

// A cleared date, seat cap or price is sent as null, which is how the API
// spells "no limit" for each.
export const formToPayload = (values: IContractForm) => ({
    ...values,
    contract_start: values.contract_start?.format(DATE_FORMAT) ?? null,
    contract_end: values.contract_end?.format(DATE_FORMAT) ?? null,
    max_learners: values.max_learners ?? null,
    enrollment_fixed_price: values.enrollment_fixed_price ?? null,
});

interface IContractFormProps {
    form: FormInstance<IContractForm>;
    onFinish: (values: IContractForm) => void;
    initialValues?: Partial<IContractForm>;
    creating: boolean;
}

export const ContractForm: React.FC<IContractFormProps> = ({ form, onFinish, initialValues, creating }) => (
    <Form<IContractForm> form={form} layout="vertical" onFinish={onFinish} initialValues={initialValues}>
        <Form.Item label="Name" name="name" rules={[{ required: true, whitespace: true, message: "Enter a name." }]}>
            <Input maxLength={255} />
        </Form.Item>
        <Form.Item
            label="Membership type"
            name="membership_type"
            rules={[{ required: true, message: "Choose how learners join the contract." }]}
            extra={
                creating
                    ? "How learners join the contract. Enrollment Code contracts get codes generated for their courseware."
                    : "Changing this on a contract with learners changes how new learners join, and whether it has enrollment codes."
            }
        >
            <Select options={CONTRACT_MEMBERSHIP_TYPES} />
        </Form.Item>
        <Form.Item label="Start date" name="contract_start" extra="Leave blank for no start date.">
            <DatePicker format={DATE_FORMAT} />
        </Form.Item>
        <Form.Item
            label="End date"
            name="contract_end"
            dependencies={["contract_start"]}
            extra="Leave blank for no end date."
            rules={[
                ({ getFieldValue }) => ({
                    validator: (_, end: Dayjs | null) => {
                        const start: Dayjs | null = getFieldValue("contract_start");
                        return start && end && end.isBefore(start, "day")
                            ? Promise.reject(new Error("The end date is before the start date."))
                            : Promise.resolve();
                    },
                }),
            ]}
        >
            <DatePicker format={DATE_FORMAT} />
        </Form.Item>
        <Form.Item label="Maximum learners" name="max_learners" extra="Leave blank or zero for unlimited.">
            <InputNumber min={0} precision={0} />
        </Form.Item>
        <Form.Item
            label="Fixed enrollment price"
            name="enrollment_fixed_price"
            extra="What a learner pays to enroll. Leave blank or zero for free."
        >
            <InputNumber<string> min="0" precision={2} stringMode prefix="$" />
        </Form.Item>
        <Form.Item label="Welcome message" name="welcome_message">
            <Input maxLength={255} />
        </Form.Item>
        <Form.Item
            label="Description"
            name="description"
            extra="Stored as HTML. Plain text is fine; keep any tags that are already there. Only text markup is kept on save: an embedded image or media is removed if you change this field."
        >
            <Input.TextArea rows={4} />
        </Form.Item>
        {!creating && (
            <Form.Item
                label="Active"
                name="active"
                valuePropName="checked"
                extra="The start and end dates still apply to an active contract."
            >
                <Switch />
            </Form.Item>
        )}
    </Form>
);
