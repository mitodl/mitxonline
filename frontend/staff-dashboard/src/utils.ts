import {IDiscount} from "./interfaces";

export const formatDiscount = (discount: IDiscount) => {
    let formattedDiscount = discount.amount;

    switch (discount.discount_type) {
        case "percent-off":
            formattedDiscount = parseFloat(discount.amount).toFixed(2) + "% off"
            break
        case "dollars-off":
            formattedDiscount = parseFloat(discount.amount).toLocaleString('en-US', { style: 'currency', currency: 'USD' }) + " off"
            break
        case "fixed-price":
            formattedDiscount = parseFloat(discount.amount).toLocaleString('en-US', { style: 'currency', currency: 'USD' }) + " fixed-price"
            break
    }
    return formattedDiscount;
}


export const formatIncome = (income: string, currency: string) => {
    return currency + " " + parseFloat(income).toLocaleString(undefined, {maximumFractionDigits: 2})
}
