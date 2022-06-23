import React from "react";
import { TitleProps, useRouterContext } from "@pankod/refine-core";

import logoImg from "../../../images/MIT-logo-black-red-72x38.svg";

export const Title: React.FC<TitleProps> = ({collapsed}) => {
  const { Link } = useRouterContext();
  return collapsed ? (
    <Link to="/">
      <img
        src={logoImg}
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
        src={logoImg}
        alt="Refine"
        style={{
          width: "200px",
          padding: "12px 24px",
        }}
      />
    </Link>
  );
}
