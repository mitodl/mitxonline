export interface IProduct {
    id: number;
    price: number;
    description: string;
    is_active: boolean;
    purchasable_object: object;
}

export interface IDiscount {
    id: number;
    discount_code: string;
    amount: string;
    discount_type: string;
    redemption_type: string;
    max_redemptions: number;
    for_flexible_pricing: boolean;
}

export interface IDiscountRedemption {
    redemption_date: string;
    redeemed_by: Object;
    redeemed_discount: Object<IDiscount>;
    redeemed_order: Object;
}

export interface IUserDiscount {
    id: number;
    discount: IDiscount;
    user: any;
}

export interface IDiscountProduct {
    id: number;
    discount: IDiscount;
    product: any;
}

export interface IDiscountProductRaw {
    id: number|null;
    discount_id: number|null;
    product_id: number|null;
}

export interface ICourseware {
    id: number;
    title: string;
    readable_id: string;
    type:string;
}


export interface IFlexiblePriceIncome {
    income_usd: string;
    original_income: string;
    original_currency: string;
}


export interface IFlexiblePriceRequest {
    id: number;
    user: number;
    courseware: ICourseware;
    status: string;
    country_of_income: null;
    date_exchange_rate: Date;
    discount: IDiscount;
    date_documents_sent: Date;
    justification: string;
    country_of_residence: string;
    action: string;
    applicable_discounts: IDiscount[];
    income: IFlexiblePriceIncome
}

export interface IFlexiblePriceStatus {
    id: string;
    title: string;
}

export interface IFlexiblePriceRequestFilters {
    q: string;
    status: string;
    courseware: string;
}

export interface IFlexiblePriceStatusModalProps {
    record: IFlexiblePriceRequest;
    status: string;
    onClose: Function;
}

export interface IDiscountFilters {
    q: string;
    redemption_type: string;
    for_flexible_pricing: string;
    is_redeemed: string;
}
