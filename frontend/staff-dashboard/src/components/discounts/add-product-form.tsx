import { 
  Table,
  useTable,
  Input,
  Col,
  Row,
} from "@pankod/refine-antd";
import { useState } from "react";

import type { IProduct } from "interfaces";

interface IAddProductFormProps {
  discountId: number;
} 

interface IProductResultProps {
  searchTerm: string;
}

const ProductResult = (props: IProductResultProps) => {
  const { searchTerm } = props;
  const { tableProps } = useTable<IProduct>({
    resource: 'products/all',
    permanentFilter: [{
      field: "q",
      operator: "eq",
      value: searchTerm
    }]
  });

  return (<Table {...tableProps} rowKey="id">
    <Table.Column
      dataIndex="id"
      title="ID" />
    <Table.Column
      dataIndex="purchasable_object"
      title="Object"
      render={(value) => (<>{value.title}<br />{value.readable_id}</>)} />
    <Table.Column
      dataIndex="price"
      title="Price" />
    <Table.Column
      dataIndex="id"
      title="" 
      render={(value) => (<button onClick={() => { console.log(`you clicked ${value}`)}}>Add</button>)}
    />
  </Table>);
}

export const AddProductForm = (props: IAddProductFormProps) => {
  const [ searchTerm, setSearchTerm ] = useState("");

  const performFilter = (ev: any) => {
    setSearchTerm(ev.target.value);
  }

  return (<>
    <Row>
      <Col sm={24}>
        <label>
          Search Products:
          <Input onChange={performFilter} allowClear={true}></Input>
        </label>
        
        {searchTerm !== "" ? (<ProductResult searchTerm={searchTerm}></ProductResult>) : null}
      </Col>
    </Row>
  </>);
}
