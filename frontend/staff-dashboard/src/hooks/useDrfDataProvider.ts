import axios, { AxiosInstance, AxiosRequestConfig } from "axios";
import {
    Pagination,
    CrudSorting,
    CrudFilters,
    CrudOperators,
    DataProvider,
} from "@pankod/refine-core"
import dataProvider from "@pankod/refine-simple-rest";
import { stringify } from "query-string";

axios.defaults.withCredentials = true;
axios.defaults.xsrfCookieName = 'csrftoken';
axios.defaults.xsrfHeaderName = 'X-CSRFToken';

const axiosInterface = axios.create();

axiosInterface.interceptors.request.use((config: AxiosRequestConfig) => {
    let token = sessionStorage.getItem(`oidc.user:${OIDC_CONFIG.authority}:${OIDC_CONFIG.client_id}`);

    if (token !== null) {
        token = JSON.parse(token).access_token;
        config.headers.Authorization = `Bearer ${token}`;
    }

    if (config.url) {
        const desturl = new URL(config.url);

        if (! desturl.pathname.endsWith('/')) {
            desturl.pathname += '/';
            config.url = desturl.href;
        }
    }

    return config;
}, (error: any) => Promise.reject(error));

const generateSort = (sort?: CrudSorting) => {
    if (sort && sort.length > 0) {
        const _sort: string[] = [];
        const _order: string[] = [];

        sort.map((item) => {
            _sort.push(item.field);
            _order.push(item.order);
        });

        return {
            _sort: _sort.join(','),
            _order: _order.join(','),
        };
    }

    return {};
};

const mapOperator = (operator: CrudOperators): string => {
    switch (operator) {
        case "ne":
        case "gte":
        case "lte":
            return `_${operator}`;
        case "contains":
            return "_like";
        case "eq":
        default:
            return "";
    }
};

const generateFilter = (filters?: CrudFilters) => {
    const queryFilters: { [key: string]: string } = {};
    if (filters) {
        filters.map((filter) => {
            if (filter.operator !== "or" && filter.value !== '') {
                const { field, operator, value } = filter;

                if (field === "q") {
                    queryFilters[field] = value;
                    return;
                }

                const mappedOperator = mapOperator(operator);
                queryFilters[`${field}${mappedOperator}`] = value;
            }
        });
    }

    return queryFilters;
};

const generatePagination = (pagination?: Pagination) => {
    const current = pagination?.current || 1;
    const pageSize = pagination?.pageSize || 3;

    return {
        o: (current - 1) * pageSize,
        l: pageSize
    };
};

const useDrfDataProvider = (
    apiUrl: string,
    httpClient: AxiosInstance = axiosInterface
): DataProvider => {
    const simpleDataProvider = dataProvider(apiUrl, httpClient);

    simpleDataProvider.getList = async ({ resource, pagination, filters, sort }) => {
        const url = `${apiUrl}/${resource}/`;

        const query = {
            ...generateFilter(filters),
            ...generateSort(sort),
            ...generatePagination(pagination),
        }

        const uri = `${url}?${stringify(query)}`;

        const { data, headers } = await httpClient.get(uri);

        if (data.hasOwnProperty('results')) {
            return {
                data: data['results'],
                total: data['count']
            };
        } else {
            return {
                data: data,
                total: data.length
            };
        }

    };

    return simpleDataProvider;
}

export default useDrfDataProvider;
