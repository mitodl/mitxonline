Overview
=========

Goals
*****

We will be creating a robust ecommerce implementation, incorporating learnings from the last several years to implement it in a scalable and reusable way. A good reference point is this guide on Pythonic SOLID Principle. We should also strongly strive towards keeping coupling between the subsystems proposed here to a minimum or at least limited in surface area.
Core

The core of the ecommerce system should be simple enough to configure and operate but support enough functionality to serve a majority of our use cases. Users should be able to see programs or course runs, select them for purchase, and make a payment.

Prior Art
*********

We have a few implementations of ecommerce we’ve created over the years:

MicroMasters
^^^^^^^^^^^^
The MicroMasters implementation is highly specialized, particularly around financial aid programs where each learner gets custom pricing. Incorporating this level of complexity into the core of the ecommerce system is not something we want to do, but we should carve out some options to extend the system in the future without implementing it in the core system.

xPro
^^^^

xPro ecommerce was implemented based on our experiences implementing ecommerce in MicroMasters. A good amount of planning went into this implementation, although it also has some specializations we wouldn’t be using in MITx Online such as a vouchers system. We will probably borrow heavily from the core designs that were proved out here.

Core Systems
************

Ecommerce is actually a combination of 3 discernable subsystems that often get muddled together: products, orders, and payment. See the high-level diagram below to understand the pieces of data and operations that happen.

.. mermaid:: assets/ecommerce-architecture.mm
