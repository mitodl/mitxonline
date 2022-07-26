import { 
  Table,
  useTable,
  List,
} from "@pankod/refine-antd";

export const Products = (props: any) => {
  const { record } = props
  const { tableProps } = useTable({
      resource: `discounts/${record?.id}/products`
  });

  return (
      <>
        <List title="Products" canCreate={false}>
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
            </Table>
        </List>
      </>
  );
}