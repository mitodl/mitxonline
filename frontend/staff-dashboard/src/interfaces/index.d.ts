export interface ILegalAddress {
    first_name: string;
    last_name: string;
    country: string;
}

export interface IUser {
    id: number;
    username: string;
    email: string;
    legal_address?: ILegalAddress;
}

export interface IProduct {
    id: number;
    price: number;
    description: string;
    is_active: boolean;
    purchasable_object: object;
}

export interface IRedeemedOrder {
    id: number;
    created_on: Date;
    updated_on: Date;
    state: string;
    total_price_paid: number;
    reference_number: string;
    purchaser: number;
}

export interface IDiscount {
    id: number;
    discount_code: string;
    amount: string;
    discount_type: string;
    redemption_type: string;
    max_redemptions: number;
    payment_type: string;
    activation_date: Date;
    expiration_date: Date;
}

export interface IDiscountRedemption {
    redemption_date: string;
    redeemed_by: Object;
    redeemed_discount: Object<IDiscount>;
    redeemed_order: IRedeemedOrder;
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

export interface IDiscountTier {
    id: number;
    discount: number;
    current: boolean;
    income_threshold_usd: number;
    courseware_object: {
        title: string;
        readable_id: string;
        id: number;
        type: string;
    }
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
    payment_type: string;
    is_redeemed: string;
}
