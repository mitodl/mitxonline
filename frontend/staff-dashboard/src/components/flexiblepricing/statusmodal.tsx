import { useUpdate, useNotification } from "@pankod/refine-core";
import React from "react"
const { useState } = React;
import {
    Select,
    Modal,
    Input
} from "@pankod/refine-antd";

import { IDiscount, IFlexiblePriceRequest, IFlexiblePriceStatusModalProps } from "interfaces";
import { formatDiscount } from "utils";
import {
    All_Justifications,
    Approved_Justifications,
    Denied_Justifications,
    DOCUMENTS_IN_ORDER,
    financialAssistanceRequestStatus
} from "../../constants";



export const FlexiblePricingStatusModal: React.FC<IFlexiblePriceStatusModalProps> = (props) => {
    const { record: modaldata, status, onClose } = props;
    const { open: displayToast } = useNotification();
    const mutationResult = useUpdate<IFlexiblePriceRequest>();
    const { mutate } = mutationResult;
    let [ emailSubject, setEmailSubject ] = useState("");
    let [ emailBody, setEmailBody ] = useState("");

    const [ justification, setJustification ] = useState(modaldata.justification);

    // set justification here to overwrite the prior state
    if (justification != DOCUMENTS_IN_ORDER && status === financialAssistanceRequestStatus.approved) {
        setJustification(DOCUMENTS_IN_ORDER);
    }
    else if (justification == DOCUMENTS_IN_ORDER && status === financialAssistanceRequestStatus.denied){
       setJustification("");
    }
    else if (justification !== "" && status === financialAssistanceRequestStatus.reset){
       setJustification("");
    }

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

    const handleOk = () => {
        if (justification.length === 0 && status !== financialAssistanceRequestStatus.reset) {
            displayToast({
                message: "Please choose a justification.",
                description: "Error",
                key: "bad-justification-error",
                type: "error",
                undoableTimeout: 3000,
            });

            return;
        }

        if (status === financialAssistanceRequestStatus.denied && (emailBody.length === 0 || emailSubject.length === 0)) {
            displayToast({
                message: "Please add email subject and body.",
                description: "Error",
                key: "bad-email-content-error",
                type: "error",
                undoableTimeout: 3000,
            });

            return;
        }

        const sendableData = {
            ...modaldata,
            status: status,
            justification: justification,
            discount: discount,
            email_subject: emailSubject,
            email_body: emailBody
        };

        mutate({
            resource: "flexible_pricing/applications_admin",
            id: sendableData.id,
            mutationMode: "optimistic",
            values: sendableData
        });
        handleCancel();
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

    const handleChangeEmailSubject = (e: string) => {
        setEmailSubject(e);
    }

    const handleChangeEmailBody = (e: string) => {
        setEmailBody(e);
    }

    return (
        <Modal title="Flexible Pricing | Management" visible={true} onOk={() => handleOk()} onCancel={handleCancel}>
            <div>
                <strong>Are you sure you want to <u>{status == financialAssistanceRequestStatus.denied ? "deny": String(status).replace(/d|ped$/, '') }</u> the request?</strong>
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
                <span><strong>Discount:</strong></span>
                {
                    status !== financialAssistanceRequestStatus.approved ?
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
                    options={ status === financialAssistanceRequestStatus.approved ? Approved_Justifications: status === financialAssistanceRequestStatus.denied?  Denied_Justifications : All_Justifications}
                    defaultValue={justification}
                >
                </Select>
            </p>
            {status === financialAssistanceRequestStatus.denied ? (
                <div>
                    <div>
                        <strong>Email Subject:</strong>
                        <Input value={emailSubject} onChange={(e) => handleChangeEmailSubject(e.target.value)}/>
                    </div>
                    <div>
                        <strong>Email Body:</strong>
                        <textarea rows={4} className="email-subject" value={emailBody} onChange={(e) => handleChangeEmailBody(e.target.value)}/>
                    </div>
                </div>
            ) : null}

        </Modal>
    );
}
