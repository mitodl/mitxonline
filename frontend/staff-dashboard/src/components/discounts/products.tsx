import { 
  Table,
  useTable,
  List,
  Button,
  Modal,
  Row,
  Col,
  Input,
} from "@pankod/refine-antd";
import { useUpdate, useDelete } from "@pankod/refine-core";
import { PlusSquareOutlined } from "@ant-design/icons";
import { useState } from "react";

import type { IProduct, IDiscountProduct } from "interfaces";

interface IProductsTableProps {
  record: any;
  isManagement?: boolean;
}

interface IProductResultProps {
  searchTerm: string;
  onAdd: Function;
}

const ProductResult = (props: IProductResultProps) => {
  const { searchTerm, onAdd } = props;
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
      render={(value, record) => (<button onClick={() => onAdd(record)}>Add</button>)}
    />
  </Table>);
}


export const Products = (props: IProductsTableProps) => {
  const { record, isManagement } = props
  const { tableProps } = useTable({
      resource: `discounts/${record?.id}/products`
  });
  const { mutate: updateProductList } = useUpdate<any>();
  const { mutate: deleteProductList } = useDelete<any>();
  const [ showAddModal, setShowAddModal ] = useState(false);
  const [ searchTerm, setSearchTerm ] = useState("");

  const performFilter = (ev: any) => {
    setSearchTerm(ev.target.value);
  }

  const hndAddProduct = (product: IProduct) => {
    updateProductList({
      id: record.id,
      resource: `discounts/${record?.id}/products`,
      values: { product_id: product.id }
    });
  }

  const hndRemoveProduct = (product: IProduct) => {
    deleteProductList({
      id: product.id,
      resource: `discounts/${record?.id}/products`,
    });
  }

  const customButtons = isManagement ? (<Button size="middle" onClick={() => setShowAddModal(true)}><PlusSquareOutlined /> Add Product</Button>) : null;

  return (
      <>
        <List title="Products" canCreate={false} pageHeaderProps={{ extra: (customButtons)}}>
            <Table {...tableProps} rowKey="id">
                <Table.Column dataIndex="id" title="ID"></Table.Column>
                <Table.Column
                  dataIndex="product"
                  title="Product Type"
                  render={(value) => value.purchasable_object.course ? "Course Run" : "Program Run" }
                ></Table.Column>
                <Table.Column
                  dataIndex="product"
                  title="Description"
                  render={(value) => value.purchasable_object.title }
                ></Table.Column>
                <Table.Column
                  dataIndex="product"
                  title="Readable ID"
                  render={(value) => value.purchasable_object.readable_id }
                ></Table.Column>
                {isManagement ? (<Table.Column dataIndex="product" title="" render={(value, record: IDiscountProduct) => (<Button size="small" onClick={() => hndRemoveProduct(record.product)}>Delete</Button>)}></Table.Column>) : null }
            </Table>
        </List>

        <Modal 
            title="Assign Products"
            visible={showAddModal}
            onCancel={() => setShowAddModal(false)}
            onOk={() => setShowAddModal(false)}
            footer={[
                <Button key="submit" type="primary" onClick={() => setShowAddModal(false)}>Close</Button>
            ]}
        >
          <Row>
            <Col sm={24}>
              <label>
                Search Products:
                <Input onChange={performFilter} allowClear={true}></Input>
              </label>
              
              {searchTerm !== "" ? (<ProductResult onAdd={hndAddProduct} searchTerm={searchTerm}></ProductResult>) : null}
            </Col>
          </Row>
        </Modal>
      </>
  );
}