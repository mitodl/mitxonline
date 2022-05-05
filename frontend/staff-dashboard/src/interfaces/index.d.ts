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