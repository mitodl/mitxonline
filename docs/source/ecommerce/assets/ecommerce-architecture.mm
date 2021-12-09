flowchart TB
    product_subsystem(Product Subsystem)
    basket_subsystem(Basket Subsystem)
    order_subsystem(Order Subsystem)
    discount_subsystem(Discount Subsystem)
    payment_subsystem(Payment Subsystem)

    cybersource(CyberSource)

    basket_subsystem --> order_subsystem
    discount_subsystem --> order_subsystem
    order_subsystem & basket_subsystem & discount_subsystem --> product_subsystem
    order_subsystem <--> payment_subsystem
    payment_subsystem <--> cybersource
