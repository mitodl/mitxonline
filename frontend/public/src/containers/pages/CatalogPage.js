import React from "react"


export class CatalogPage extends React.Component<Props> {
  state = {
    tabSelected: "courses"
  }

  changeSelectedTab = (btn: string) => {
    this.setState({ tabSelected: btn })
  };

  render() {
    return (
      <div id="catalog-page">
        <div id="catalog-title">
          <h1>MITx Online Catalog</h1>
        </div>
        <div id="course-catalog-navigation">
          <div id="department-sidebar">
            <ul id="department-sidebar-link-list">
              <li className="department-selected-link">All Departments</li>
              <li className="department-link">Tea</li>
              <li className="department-link">Milk</li>
            </ul>
          </div>
          <div id="tab-count-row">
            <div id="tabs">
              <div className={this.state.tabSelected === "courses" ? "selected-tab" : "unselected-tab"}>
                <button onClick={() => this.changeSelectedTab("courses")}>Courses</button>
              </div>
              <div className={this.state.tabSelected === "programs" ? "selected-tab" : "unselected-tab"}>
                <button onClick={() => this.changeSelectedTab("programs")}>Programs</button>
              </div>
            </div>
            <div id="catalog-page-item-count">
              18 courses
            </div>
          </div>
        </div>
      </div>
    )
  }
}
export default CatalogPage
