sequenceDiagram
    participant MO as MITx Online
    participant OE as Open edX

    par Create Account in Open edx
        MO->>OE: POST /user_api/v1/account/registration/
        OE-->>MO: Success
    end

    par Create Open edX Access Token
        Note right of MO: Create in-memory requests session
        par Establish an Open edX session
            MO->>OE: GET /auth/login/mitxpro-oauth2/?auth_entry=login
            OE->>MO: Redirect to GET /oauth2/authorize
            MO->>OE: Redirect to GET /auth/complete/mitxpro-oauth2/
        end

        par Link MITx Online account to Open edX Account
            MO->>OE: GET /oauth2/authorize
            OE-->>MO: Redirect to GET /login/_private/complete
            MO->>OE: POST /oauth2/access_token
            OE-->>MO: OAuth access and refresh tokens
        end

    end
