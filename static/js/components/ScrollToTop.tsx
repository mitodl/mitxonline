import React, { ReactNode, useEffect } from "react"
import { useLocation } from "react-router"

type Props = {
  children: ReactNode | ReactNode[]
}

export default function ScrollToTop({ children }: Props): JSX.Element {
  const { pathname } = useLocation()

  useEffect(() => {
    window.scrollTo(0, 0)
  }, [pathname])

  return <>{children}</>
}
