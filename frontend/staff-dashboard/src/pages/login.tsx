
import { useLogin, useTitle } from "@pankod/refine-core";
import { AntdLayout, Button, Icons, Space, Typography } from "@pankod/refine-antd";

const { LoginOutlined } = Icons;


export default function LoginPage() {
    const Title = useTitle();
    const { mutate: login, isLoading } = useLogin();
    return (
        <AntdLayout>
            <div style={{ height: "100vh", display: "flex" }}>
                <div style={{ maxWidth: "300px", margin: "auto", textAlign: "center" }}>
                    {Title && <Title collapsed={false} />}
                    <Space/>
                    <Typography.Title>MITx Online<br/>Staff Dashboard</Typography.Title>
                    <Space/>
                    <Button
                        type="primary"
                        size="large"
                        block
                        icon={<LoginOutlined />}
                        loading={isLoading}
                        onClick={() => login({})}
                    >
                        Sign in
                    </Button>
                </div>
            </div>
        </AntdLayout>
    );
};