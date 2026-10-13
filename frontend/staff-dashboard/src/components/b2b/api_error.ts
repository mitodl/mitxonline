interface IApiErrorBody {
    detail?: string;
    errors?: string[] | Record<string, unknown>;
}

const messages = (value: unknown) => (Array.isArray(value) ? value.join(" ") : JSON.stringify(value));

// What the provisioning API said about a failed request: a 400 carries
// `errors`, by field or as a list, and everything else carries `detail`.
export const apiErrorDescription = (error: unknown): string => {
    const body = (error as { response?: { data?: IApiErrorBody } })?.response?.data;

    if (body?.detail) {
        return body.detail;
    }
    if (Array.isArray(body?.errors)) {
        return messages(body?.errors);
    }
    if (body?.errors) {
        return Object.entries(body.errors)
            .map(([field, value]) => (field === "non_field_errors" ? messages(value) : `${field}: ${messages(value)}`))
            .join(" ");
    }
    return (error as Error)?.message ?? "";
};
