import { useUpdate, useNotification } from "@pankod/refine-core";
import React from "react"
const { useState } = React;
import {
    Select,
    Modal
} from "@pankod/refine-antd";

import {IDiscount, IFlexiblePriceRequest, IFlexiblePriceStatusModalProps} from "interfaces";
import {formatDiscount, formatIncome} from "utils";

const All_Justifications = [
    {
        label: '',
        value: '',
    },
    {
        label: 'Documents in order',
        value: 'Documents in order'
    },
    {
        label: 'Docs not notarized',
        value: 'Docs not notarized'
    },
    {
        label: 'Insufficient docs',
        value: 'Insufficient docs'
    },
    {
        label: 'Inaccurate income reported',
        value: 'Inaccurate income reported'
    },
    { 
        label: 'Inaccurate country reported',
        value: 'Inaccurate country reported'
    },
];


export const FlexiblePricingStatusModal: React.FC<IFlexiblePriceStatusModalProps> = (props) => {
    const { record: modaldata, status, onClose } = props;
    const { open: displayToast } = useNotification();
    const mutationResult = useUpdate<IFlexiblePriceRequest>();
    const { mutate } = mutationResult;

    let [ justification, setJustification ] = useState(modaldata.justification);
    !justification && status === "approved" ? setJustification("Documents in order") : null

    const [ discount, setDiscount ] = useState(modaldata.discount);
    let discount_choices = [];
    for (let applicable_discount of modaldata.applicable_discounts) {
        discount_choices.push(
            {
                "value": applicable_discount.id,
                "label": formatDiscount(applicable_discount)
            }
        )
    }

    const handleCancel = () => {
        onClose();
    }

    const handleChangeJustification = (e: string) => {
        setJustification(e);
    }

    const handleChangeDiscount = (e: number) => {
        const selected_discount_label = modaldata.applicable_discounts.find(discount_option => {
            return discount_option.id === e
        })
        setDiscount(selected_discount_label as IDiscount);
    }

    const handleOk = () => {
        if (justification.length === 0) {
            displayToast({
                message: "Please choose a justification.",
                description: "Error",
                key: "bad-justification-error",
                type: "error",
                undoableTimeout: 3000,
            });

            return;
        }

        const sendableData = { ...modaldata, status: status, justification: justification, discount: discount };

        mutate({ 
            resource: "flexible_pricing/applications_admin",
            id: sendableData.id,
            mutationMode: "undoable",
            values: sendableData
        });
        handleCancel();
    }

    return (
        <Modal title="Flexible Pricing | Management" visible={true} onOk={() => handleOk()} onCancel={handleCancel}>
            <div>
                <strong>Are you sure you want to <u>{status == "denied" ? "deny": String(status).replace(/d|ped$/, '') }</u> the request?</strong>
                {status == "denied" ? <div>User will be notified by email of the denial </div> : null}
            </div>
            <br></br>
            <p>
                <strong>Courseware:</strong>
                <div>{modaldata.courseware.readable_id}</div>
            </p>
            <p>
                <strong>Current Status:</strong>
                <div>{modaldata.status}</div>
            </p>
            <p>
                <strong>Income USD:</strong>
                <div>{formatIncome(modaldata.income.income_usd, "USD")}</div>
            </p>
            <p>
                <strong>Original Income:</strong>
                <div>{formatIncome(modaldata.income.original_income, modaldata.income.original_currency)}</div>
            </p>
            <p>
                <strong>Original Currency:</strong>
                <div>{modaldata.income.original_currency}</div>
            </p>
            <p>
                <strong>Country of Income:</strong>
                <div>{modaldata.country_of_income}</div>
            </p>
            <p>
                <span><strong>Discount:</strong></span>
                {
                    status !== "approved" ?
                        <div>{ formatDiscount(modaldata.discount) }</div> :
                        <Select
                            onChange={(e) => handleChangeDiscount(e)}
                            style={{ marginLeft: "44px", 'width': '20rem' }}
                            options={discount_choices}
                            defaultValue={modaldata.discount.id}
                        >
                        </Select>
                }
            </p>
            <p>
                <span>
                    <strong>Justification:</strong>
                </span>
                <Select 
                    onChange={(e) => handleChangeJustification(e)} 
                    style={{ marginLeft: "20px", 'width': '20rem' }}
                    options={All_Justifications}
                    defaultValue={justification}
                >
                </Select>
            </p>
        </Modal>
    );
}
