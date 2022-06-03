import React from "react";
import { TitleProps, useRouterContext } from "@pankod/refine-core";

export const Title: React.FC<TitleProps> = ({collapsed}) => {
  const { Link } = useRouterContext();
  return collapsed ? (
    <Link to="/">
      <img
        src={"/MIT-logo-black-red-72x38.svg"}
        alt="Refine"
        style={{
          width: "80px",
          padding: "12px 24px",
        }}
      />
    </Link>
  ) : (
    <Link to="/">
      <img
        src={"/MIT-logo-black-red-72x38.svg"}
        alt="Refine"
        style={{
          width: "200px",
          padding: "12px 24px",
        }}
      />
    </Link>
  );
}
