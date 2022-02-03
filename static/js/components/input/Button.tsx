import React from "react"

type ButtonProps = {
  children: React.ReactElement<React.ComponentProps<any>, any>
  onClick: (...args: Array<any>) => any
  className?: string
}

const Button = ({ children, onClick, className }: ButtonProps) => (
  <button className={`mdc-button ${className || ""}`} onClick={onClick}>
    {children}
  </button>
)

export default Button
