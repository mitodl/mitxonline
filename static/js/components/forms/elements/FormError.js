import React from "react"

type Props = {
  children: any
}

export default class FormError extends React.Component<Props> {
  render() {
    const { children, id } = this.props
    return (
      <div className="form-error" id={id} role="alert">
        {children}
      </div>
    )
  }
}
