import React from "react"

type Props = {
  productId: number
}

const GetCertificateButton = ({ productId }: Props) => {
  return (
    <form
      action="/cart/add/"
      method="get"
      className="text-center ml-auto"
    >
      <input
        type="hidden"
        name="product_id"
        value={productId}
      />
      <button
        type="submit"
        className="btn btn-primary btn-gradient-red"
      >
        Get Certificate
      </button>
    </form>
  )
}

export default GetCertificateButton
