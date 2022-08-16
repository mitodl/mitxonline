import {IDiscount} from "./interfaces";

export const formatDiscount = (discount: IDiscount) => {
    let formattedDiscount = discount.amount;

    switch (discount.discount_type) {
        case "percent-off":
            formattedDiscount = parseFloat(discount.amount).toFixed(2) + "% off"
            break
        case "dollars-off":
            formattedDiscount = formatIncome(discount.amount, "USD") + " off"
            break
        case "fixed-price":
            formattedDiscount = formatIncome(discount.amount, "USD") + " fixed-price"
            break
    }
    return formattedDiscount;
}


export const formatIncome = (income: string, currency: string) => {
    return parseFloat(income).toLocaleString("en-US", {style: "currency", currency: currency})
}
