import { History } from "history"
import React, { ReactNode } from "react"
import { Provider } from "react-redux"
import { Route, Router as ReactRouter } from "react-router"
import { Provider as ReduxQueryProvider } from "redux-query-react"
import ScrollToTop from "./components/ScrollToTop"
import App from "./containers/App"
import { NotificationsProvider } from "./hooks/notifications"
import { getQueries } from "./lib/redux_query"
import { Store } from "./store/configureStore"

type Props = {
  history: History
  store: Store
  children: ReactNode
}

export default function Root({ children, store, history }: Props) {
  return (
    <div>
      <Provider store={store}>

        <ReduxQueryProvider queriesSelector={getQueries}>
          <NotificationsProvider>
            <ReactRouter history={history}>
              <ScrollToTop>{children}</ScrollToTop>
            </ReactRouter>
          </NotificationsProvider>
        </ReduxQueryProvider>
      </Provider>
    </div>
  )
}

export const routes = <Route path="/" component={App} />
