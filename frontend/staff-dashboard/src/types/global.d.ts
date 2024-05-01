import { OidcClientSettings } from "oidc-client-ts";

type DatasourceSettings = {
    mitxOnline: string
}
export declare global {
    var OIDC_CONFIG: OidcClientSettings
    var DATASOURCES_CONFIG: DatasourceSettings
}
