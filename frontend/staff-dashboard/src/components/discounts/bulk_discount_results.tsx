import { Show, Row, Col } from "@pankod/refine-antd";
import {
  Table,
  Button,
  Card,
} from "@pankod/refine-antd";

import fileDownload from 'js-file-download';

import type { IDiscount } from "interfaces"

const Papa = require("papaparse");

interface IBulkDiscountResultsProps {
  data: any;
}

export const BulkDiscountResults = (props: IBulkDiscountResultsProps) => {
  const { data } = props;

  const deliverData = () => {
    const jsonedData = JSON.stringify(data);
    const toCSV = Papa.unparse(jsonedData);
    fileDownload(toCSV, "MITx Online Generated Codes.csv");
  }

  const columns = [
    { title: "Code", dataIndex: "discount_code", key: "discount_code" },
    { title: "Amount", render: (text: any, record: IDiscount, index: any) => {
        return (<>{record.discount_type != 'percent-off' ? '$' : null}{record.amount}{record.discount_type == 'percent-off' ? '%' : null} {record.discount_type}</>)
      }, key: "discount_value" },
    { title: "Redemption", dataIndex: "redemption_type", key: "redemption_type" },
    { title: "Purpose", dataIndex: "payment_type", key: "payment_type" },
    { title: "Activates", dataIndex: "activation_date", key: "activation_date" },
    { title: "Expires", dataIndex: "expiration_date", key: "expiration_date" }
  ];

  return (<>
    <Card>
      <h2>Discounts Created</h2>

      <Row>
        <Col span={24}>
          <p>{data ? data.length : 0} discounts were created. <a href="#" onClick={() => { window.location.reload(); }}>Create More</a></p>
        </Col>
      </Row>

      <Row>
        <Col span={24}>
          <Table size="large" columns={columns} dataSource={data}></Table>
        </Col>
      </Row>

      <Row justify="end">
        <Col>
          <Button onClick={deliverData}>Download as CSV</Button>
        </Col>
      </Row>
    </Card>
  </>);
}
