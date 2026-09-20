# Carriers

Each adapter in `shipdesk/carriers/` holds a rate table per zone. A weight band's limit is inclusive: a
500 g parcel is priced in the 500 g band. Carriers that cannot carry a parcel raise `WeightLimitExceeded`;
`registry.cheapest` skips them.
