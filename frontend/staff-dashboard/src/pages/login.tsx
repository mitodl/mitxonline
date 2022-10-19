export default function LoginPage() {
    const sign_in_url = (new URL(DATASOURCES_CONFIG.mitxOnline)).origin + "/signin/?next=/staff-dashboard/";

    document.location = sign_in_url;
    
    return (<>Please wait while we redirect you to the sign in page...</>);
    
};