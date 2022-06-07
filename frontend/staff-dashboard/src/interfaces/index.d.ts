export interface IDiscount {
    id: int;
    discount_code: string;
    amount: float;
    discount_type: string;
    redemption_type: string;
    max_redemptions: int;
}

export interface IDiscountRedemption {
    redemption_date: string;
    redeemed_by: Object;
    redeemed_discount: Object<IDiscount>;
    redeemed_order: Object;
}

export interface IUserDiscount {
    id: int;
    discount: IDiscount;
    user: any;
}

export interface IFlexiblePriceRequest {
    id: number;
    user: number;
    status: string;
    income_usd: number;
    original_income: number;
    original_currency: string;
    country_of_income: null;
    date_exchange_rate: Date;
    date_documents_sent: Date;
    justification: string;
    country_of_residence: string;
    action: string
}

export interface IFlexiblePriceStatus {
    id: string;
    title: string;
}

export interface IFlexiblePriceRequestFilters {
    q: string;
    status: string;
}