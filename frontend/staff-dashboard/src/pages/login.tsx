
import { useLogin } from "@pankod/refine-core";
import { AntdLayout, Button, Icons, Space, Title } from "@pankod/refine-antd";

const { LoginOutlined } = Icons;


export default function LoginPage() {
    const { mutate: login, isLoading } = useLogin();
    return (
        <AntdLayout
            style={{
                background: `radial-gradient(50% 50% at 50% 50%, #63386A 0%, #310438 100%)`,
                backgroundSize: "cover",
            }}
        >
            <div style={{ height: "100vh", display: "flex" }}>
                <div style={{ maxWidth: "200px", margin: "auto" }}>
                    <Title collapsed={false}>
                        MITx Online Internal Dashboard
                    </Title>
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