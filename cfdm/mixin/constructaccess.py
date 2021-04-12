import logging
import re

logger = logging.getLogger(__name__)


class ConstructAccess:
    """Mixin to manipulate constructs stored in a `Constructs` object.

    .. versionadded:: (cfdm) 1.7.0

    """

    def _filter_interface(
        self,
        _ctypes,
        _method,
        identities,
        cached=None,
        construct=False,
        key=False,
        item=False,
        default=None,
        _last_filter=None,
        _identity_config={},
        **filter_kwargs,
    ):
        """An optimised interface to `Constructs.filter`.

        .. versionadded:: (cfdm) 1.8.9.0

        :Parameters:

            _ctypes: `tuple` of `str`
                The construct types to restrict the selection to.

            _method: `str`
                The name of the calling method.

            identities: `tuple`
                Select constructs that have an identity, defined by
                their `!identities` methods, that matches any of the
                given tuple values.

                {{value match}}

            {{todict: `bool`, optional}}

            {{cached: optional}}

            {{filter_kwargs: optional}}

        :Returns:

            `Constructs` or `dict` or *cached*
                If *cached* is `None`, return the selected
                constructs. If *cached* is not `None`, return
                *cached*.

        """
        if cached is not None:
            return cached

        if not _ctypes:
            kwargs = filter_kwargs
        else:
            # Ensure that filter_by_types is the first filter
            # applied, as it's the cheapest
            if not (identities or filter_kwargs):
                # Calling filter_by_type directly is faster
                if construct:
                    todict = True
                else:
                    todict = False

                c = self.constructs.filter_by_type(*_ctypes, todict=todict)

                if not construct:
                    # Return Constructs or dict
                    return c

                # Return constuct, or key, or both, or default
                n = len(c)
                if n == 1:
                    k, construct = c.popitem()
                    if key:
                        return k

                    if item:
                        return k, construct

                    return construct

                if default is None:
                    return default

                return self._default(
                    default,
                    f"{self.__class__.__name__}.{_method}() can't return {n} "
                    "constructs",
                )

            kwargs = {"filter_by_type": _ctypes}

            if filter_kwargs:
                if "filter_by_type" in filter_kwargs:
                    raise TypeError(
                        f"{self.__class__.__name__}.{_method}() got an "
                        "unexpected keyword argument 'filter_by_type'"
                    )

                kwargs.update(filter_kwargs)

        # Ensure that filter_by_identity is the one of the last
        # filters applied, as it's expensive.
        filter_by_identity = kwargs.pop("filter_by_identity", None)
        if filter_by_identity is None:
            if identities:
                kwargs["filter_by_identity"] = identities
        else:
            kwargs["filter_by_identity"] = filter_by_identity
            if identities:
                raise TypeError(
                    f"Can't set {self.__class__.__name__}.{_method}() "
                    "keyword argument 'filter_by_identity' when "
                    "positional *identities arguments are also set"
                )

        if _last_filter:
            for ftype in _last_filter:
                value = kwargs.pop(ftype, None)
                if value is not None:
                    kwargs[ftype] = value

        if construct:
            kwargs["todict"] = True

        c = self.constructs.filter(
            _identity_config=_identity_config,
            **kwargs,
        )

        if not construct:
            # Return Constructs or dict
            return c

        # Return constuct, or key, or both, or default
        n = len(c)
        if n == 1:
            k, construct = c.popitem()
            if key:
                return k

            if item:
                return k, construct

            return construct

        if default is None:
            return default

        return self._default(
            default,
            f"{self.__class__.__name__}.{_method}() can't return {n} "
            "constructs",
        )

    #    def _select_construct(
    #        self,
    #        _ctypes,
    #        _method,
    #        identities,
    #        key=False,
    #        default=None,
    #        item=False,
    #        todict=False,
    #        cached=None,
    #        _last_filter=None,
    #        _identity_config={},
    #        **filter_kwargs,
    #    ):
    #        """An optimised interface for selecting a unique construct.
    #
    #        .. versionadded:: (cfdm) 1.8.9.0
    #
    #        :Parameters:
    #
    #            _ctypes: `tuple` of `str`
    #                The construct types to restrict the selection to.
    #
    #            _method: `str`
    #                The name of the calling method.
    #
    #            identities: `tuple`
    #                Select constructs that have an identity, defined by
    #                their `!identities` methods, that matches any of the
    #                given tuple values.
    #
    #                {{value match}}
    #
    #            default: optional
    #                Return the value of the *default* parameter if there
    #                is no unique construct.
    #
    #                {{default Exception}}
    #
    #            key: `bool`, optional
    #                If True the return the construct identifier.
    #
    #            item: `bool`, optional
    #                If True the return the construct identifier and the
    #                construct.
    #
    #            {{todict: `bool`, optional}}
    #
    #            {{cached: optional}}
    #
    #            {{filter_kwargs: optional}}
    #
    #        :Returns:
    #
    #                The unique construct, or its identifier, or both.
    #
    #        """
    #        if cached is not None:
    #            return cached
    #
    #        filter_kwargs["todict"] = True
    #
    #        c = self._filter_interface(
    #            _ctypes,
    #            _method,
    #            identities,
    #            cached=cached,
    #            _last_filter=_last_filter,
    #            _identity_config=_identity_config,
    #            **filter_kwargs,
    #        )
    #
    #        n = len(c)
    #        if n == 1:
    #            k, construct = c.popitem()
    #            if key:
    #                return k
    #
    #            if item:
    #                return k, construct
    #
    #            return construct
    #
    #        if default is None:
    #            return default
    #
    #        return self._default(
    #            default,
    #            f"{self.__class__.__name__}.{_method}() can't return {n} "
    #            "constructs",
    #        )

    def _unique_construct_names(self):
        """Return unique metadata construct names.

        .. versionadded:: (cfdm) 1.7.0

        **Examples:**

        >>> f._unique_construct_names()
        {'cellmethod0': 'method:mean',
         'dimensioncoordinate0': 'latitude',
         'dimensioncoordinate1': 'longitude',
         'dimensioncoordinate2': 'time',
         'domainaxis0': 'ncdim%lat',
         'domainaxis1': 'ncdim%lon',
         'domainaxis2': 'key%domainaxis2'}

        """
        key_to_name = {}
        ignore = self.constructs._ignore

        for ctype, d in self.constructs._constructs.items():
            if ctype in ignore:
                continue

            name_to_keys = {}

            for key, construct in d.items():
                name = construct.identity(default="key%" + key)
                name_to_keys.setdefault(name, []).append(key)
                key_to_name[key] = name

            for name, keys in name_to_keys.items():
                if len(keys) <= 1:
                    continue

                for key in keys:
                    key_to_name[key] = "{0}{{{1}}}".format(
                        name, re.findall(r"\d+$", key)[0]
                    )

        return key_to_name

    def _unique_domain_axis_identities(self):
        """Return unique domain axis construct names.

        .. versionadded:: (cfdm) 1.7.0

        **Examples:**

        >>> f._unique_domain_axis_identities()
        {'domainaxis0': 'latitude(5)',
         'domainaxis1': 'longitude(8)',
         'domainaxis2': 'time(1)'}

        """
        key_to_name = {}
        name_to_keys = {}

        for key, value in self.domain_axes(todict=True).items():
            name_size = (
                self.constructs.domain_axis_identity(key),
                value.get_size(""),
            )
            name_to_keys.setdefault(name_size, []).append(key)
            key_to_name[key] = name_size

        for (name, size), keys in name_to_keys.items():
            if len(keys) == 1:
                key_to_name[keys[0]] = f"{name}({size})"
            else:
                for key in keys:
                    key_to_name[key] = "{0}{{{1}}}({2})".format(
                        name, re.findall(r"\d+$", key)[0], size
                    )

        return key_to_name

    def coordinate_references(self, *identities, **filter_kwargs):
        """Return coordinate reference constructs.

        .. versionadded:: (cfdm) 1.7.0

        .. seealso:: `constructs`

        :Parameters:

            identities: optional
                Select coordinate reference constructs that have an
                identity, defined by their `!identities` methods, that
                matches any of the given values.

                If no identities are provided then all coordinate
                reference constructs are selected.

                {{value match}}

                {{displayed identity}}

            {{filter_kwargs: optional}}

        :Returns:

            `Constructs`
                The selected constructs, unless modified by any
                *filter_kwargs* parameters.

        **Examples:**

        >>> f.coordinate_references()
        Constructs:
        {}

        >>> f.coordinate_references()
        Constructs:
        {'coordinatereference0': <{{repr}}CoordinateReference: atmosphere_hybrid_height_coordinate>,
         'coordinatereference1': <{{repr}}CoordinateReference: rotated_latitude_longitude>}

        """
        return self._filter_interface(
            ("coordinate_reference",),
            "coordinate_references",
            identities,
            **filter_kwargs,
        )

    def del_construct(self, *identity, default=ValueError(), **filter_kwargs):
        """Remove a metadata construct.

        If a domain axis construct is selected for removal then it
        can't be spanned by any data arrays of the field nor metadata
        constructs, nor be referenced by any cell method
        constructs. However, a domain ancillary construct may be
        removed even if it is referenced by coordinate reference
        construct.

        .. versionadded:: (cfdm) 1.7.0

        .. seealso:: `get_construct`, `constructs`, `has_construct`,
                     `set_construct`

        :Parameters:

            identity:
                Select the unique construct that has the identity,
                defined by its `!identities` method, that matches the
                given values.

                Additionally, the values are matched against construct
                identifiers, with or without the ``'key%'`` prefix.

                {{value match}}

                {{displayed identity}}

            default: optional
                Return the value of the *default* parameter if the
                data axes have not been set.

                {{default Exception}}

            {{filter_kwargs: optional}}

        :Returns:

                The removed metadata construct.

        **Examples:**

        >>> f = {{package}}.example_field(0)
        >>> print(f)
        Field: specific_humidity (ncvar%q)
        ----------------------------------
        Data            : specific_humidity(latitude(5), longitude(8)) 1
        Cell methods    : area: mean
        Dimension coords: latitude(5) = [-75.0, ..., 75.0] degrees_north
                        : longitude(8) = [22.5, ..., 337.5] degrees_east
                        : time(1) = [2019-01-01 00:00:00]
        >>> f.del_construct('time')
        <{{repr}}DimensionCoordinate: time(1) days since 2018-12-01 >
        >>> f.del_construct('time')
        Traceback (most recent call last):
            ...
        ValueError: Can't remove non-existent construct 'ti
        >>> f.del_construct('time', default='No time')
        'No time'
        >>> f.del_construct('dimensioncoordinate1')
        <{{repr}}DimensionCoordinate: longitude(8) degrees_east>
        >>> print(f)
        Field: specific_humidity (ncvar%q)
        ----------------------------------
        Data            : specific_humidity(latitude(5), ncdim%lon(8)) 1
        Cell methods    : area: mean
        Dimension coords: latitude(5) = [-75.0, ..., 75.0] degrees_north

        """
        key = self.construct_key(*identity, default=None, **filter_kwargs)
        if key is not None:
            return self.constructs._del_construct(key)

        if default is None:
            return default

        return self._default(default, "Can't find unique construct to remove")

    def domain_axes(self, *identities, **filter_kwargs):
        """Return domain axis constructs.

        .. versionadded:: (cfdm) 1.7.0

        .. seealso:: `constructs`

        :Parameters:

            identities: `tuple`, optional
                Select domain axis constructs that have an identity,
                defined by their `!identities` methods, that matches
                any of the given values.

                {{value match}}

                {{displayed identity}}

            {{filter_kwargs: optional}}

        :Returns:

            `Constructs`
                The selected constructs, unless modified by any
                *filter_kwargs* parameters.

        **Examples:**

        >>> f.domain_axes()
        Constructs:
        {}

        >>> f.domain_axes()
        Constructs:
        {'domainaxis0': <{{repr}}DomainAxis: size(1)>,
         'domainaxis1': <{{repr}}DomainAxis: size(10)>,
         'domainaxis2': <{{repr}}DomainAxis: size(9)>,
         'domainaxis3': <{{repr}}DomainAxis: size(1)>}

        """
        return self._filter_interface(
            ("domain_axis",), "domain_axes", identities, **filter_kwargs
        )

    def auxiliary_coordinates(self, *identities, **filter_kwargs):
        """Return auxiliary coordinate constructs.

        .. versionadded:: (cfdm) 1.7.0

        .. seealso:: `constructs`

        :Parameters:

            identities: optional
                Select auxiliary coordinate constructs that have an
                identity, defined by their `!identities` methods, that
                matches any of the given values.

                If no identities are provided then all auxiliary
                coordinate constructs are selected.

                {{value match}}

                {{displayed identity}}

            {{filter_kwargs: optional}}

        :Returns:

            `Constructs`
                The selected constructs, unless modified by any
                *filter_kwargs* parameters.

        **Examples:**

        >>> f.auxiliary_coordinates()
        Constructs:
        {}

        >>> f.auxiliary_coordinates()
        Constructs:
        {'auxiliarycoordinate0': <{{repr}}AuxiliaryCoordinate: latitude(10, 9) degrees_N>,
         'auxiliarycoordinate1': <{{repr}}AuxiliaryCoordinate: longitude(9, 10) degrees_E>,
         'auxiliarycoordinate2': <{{repr}}AuxiliaryCoordinate: long_name:Grid latitude name(10) >}

        """
        return self._filter_interface(
            ("auxiliary_coordinate",),
            "auxiliary_coordinates",
            identities,
            **filter_kwargs,
        )

    def dimension_coordinates(self, *identities, **filter_kwargs):
        """Return dimension coordinate constructs.

        .. versionadded:: (cfdm) 1.7.0

        .. seealso:: `constructs`

        :Parameters:

            identities: optional
                Select dimension coordinate constructs that have an
                identity, defined by their `!identities` methods, that
                matches any of the given values.

                If no identities are provided then all dimension
                coordinate constructs are selected.

                {{value match}}

                {{displayed identity}}

            {{filter_kwargs: optional}}

        :Returns:

            `Constructs`
                The selected constructs, unless modified by any
                *filter_kwargs* parameters.

        **Examples:**

        >>> f.dimension_coordinates()
        Constructs:
        {}

        >>> f.dimension_coordinates()
        Constructs:
        {'dimensioncoordinate0': <{{repr}}DimensionCoordinate: atmosphere_hybrid_height_coordinate(1) >,
         'dimensioncoordinate1': <{{repr}}DimensionCoordinate: grid_latitude(10) degrees>,
         'dimensioncoordinate2': <{{repr}}DimensionCoordinate: grid_longitude(9) degrees>,
         'dimensioncoordinate3': <{{repr}}DimensionCoordinate: time(1) days since 2018-12-01 >}

        """
        return self._filter_interface(
            ("dimension_coordinate",),
            "dimension_coordinates",
            identities,
            **filter_kwargs,
        )

    def coordinates(self, *identities, **filter_kwargs):
        """Return dimension and auxiliary coordinate constructs.

        . versionadded:: (cfdm) 1.7.0

        . seealso:: `auxiliary_coordinates`, `constructs`,
                    `dimension_coordinates`

        :Parameters:

            identities: optional
                Select coordinate constructs that have an identity,
                defined by their `!identities` methods, that matches
                any of the given values.

                If no identities are provided then all coordinate
                constructs are selected.

                {{value match}}

                {{displayed identity}}

            {{filter_kwargs: optional}}

        :Returns:

            `Constructs`
                The selected constructs, unless modified by any
                *filter_kwargs* parameters.

        *Examples:**

        >> f.coordinates()
        onstructs:
        }

        >> f.coordinates()
        onstructs:
        'auxiliarycoordinate0': <{{repr}}AuxiliaryCoordinate: latitude(10, 9) degrees_N>,
        'auxiliarycoordinate1': <{{repr}}AuxiliaryCoordinate: longitude(9, 10) degrees_E>,
        'auxiliarycoordinate2': <{{repr}}AuxiliaryCoordinate: long_name=Grid latitude name(10) >,
        'dimensioncoordinate0': <{{repr}}DimensionCoordinate: atmosphere_hybrid_height_coordinate(1) >,
        'dimensioncoordinate1': <{{repr}}DimensionCoordinate: grid_latitude(10) degrees>,
        'dimensioncoordinate2': <{{repr}}DimensionCoordinate: grid_longitude(9) degrees>,
        'dimensioncoordinate3': <{{repr}}DimensionCoordinate: time(1) days since 2018-12-01 >}

        """
        return self._filter_interface(
            (
                "dimension_coordinate",
                "auxiliary_coordinate",
            ),
            "coordinates",
            identities,
            **filter_kwargs,
        )

    def domain_ancillaries(self, *identities, **filter_kwargs):
        """Return domain ancillary constructs.

        .. versionadded:: (cfdm) 1.7.0

        .. seealso:: `constructs`

        :Parameters:

            identities: optional
                Select domain ancillary constructs that have an
                identity, defined by their `!identities` methods, that
                matches any of the given values.

                {{value match}}

                {{displayed identity}}

            {{filter_kwargs: optional}}

        :Returns:

            `Constructs`
                The selected constructs, unless modified by any
                *filter_kwargs* parameters.

        **Examples:**

        >>> f.domain_ancillaries()
        Constructs:
        {}

        >>> f.domain_ancillaries()
        Constructs:
        {'domainancillary0': <{{repr}}DomainAncillary: ncvar%a(1) m>,
         'domainancillary1': <{{repr}}DomainAncillary: ncvar%b(1) >,
         'domainancillary2': <{{repr}}DomainAncillary: surface_altitude(10, 9) m>}

        """
        return self._filter_interface(
            ("domain_ancillary",),
            "domain_ancillaries",
            identities,
            **filter_kwargs,
        )

    def cell_measures(self, *identities, **filter_kwargs):
        """Return cell measure constructs.

        ``c.cell_measures(*identities, **filter_kwargs)`` is
        equivalent to
        ``c.constructs.filter(filter_by_type=["cell_measure"],
        filter_by_identity=identities, **filter_kwargs)``.

        .. versionadded:: (cfdm) 1.7.0

        .. seealso:: `constructs`

        :Parameters:

            identities: optional
                Select cell measure constructs that have an identity,
                defined by their `!identities` methods, that matches
                any of the given values.

                If no identities are provided then all cell measure
                constructs are selected.

                {{value match}}

                {{displayed identity}}

            {{filter_kwargs: optional}}

        :Returns:

            `Constructs`
                The selected constructs, unless modified by any
                *filter_kwargs* parameters.

        **Examples:**

        >>> f.cell_measures()
        Constructs:
        {}

        >>> f.cell_measures()
        Constructs:
        {'cellmeasure0': <{{repr}}CellMeasure: measure%area(9, 10) km2>}

        """
        return self._filter_interface(
            ("cell_measure",), "cell_measures", identities, **filter_kwargs
        )

    def construct(self, *identity, default=ValueError(), **filter_kwargs):
        """Return a metadata construct.

        If zero or two or more constructs are selected then an
        exception is raised, or the *default* parameter is returned.

        All constructs that

        .. versionadded:: (cfdm) 1.7.0

        .. seealso:: `construct_key`, `constructs`

        :Parameters:

            identity: optional
                Select constructs that have an identity, defined by
                their `!identities` methods, that matches any of the
                given values.

                Additionally, the values are matched against construct
                identifiers, with or without the ``'key%'`` prefix.

                If no values are provided then all constructs are
                selected.

                {{value match}}

                {{displayed identity}}

            default: optional
                Return the value of the *default* parameter if there
                is no unique construct.

                {{default Exception}}

            {{filter_kwargs: optional}}

        :Returns:

                The selected construct.

        **Examples:**

        >>> print(f.constructs)
        Constructs:
        {'cellmethod0': {{repr}}<CellMethod: area: mean>,
         'dimensioncoordinate0': <{{repr}}DimensionCoordinate: latitude(5) degrees_north>,
         'dimensioncoordinate1': <{{repr}}DimensionCoordinate: longitude(8) degrees_east>,
         'dimensioncoordinate2': <{{repr}}DimensionCoordinate: long_name=time(1) days since 2018-12-01 >,
         'domainaxis0': <{{repr}}DomainAxis: size(5)>,
         'domainaxis1': <{{repr}}DomainAxis: size(8)>,
         'domainaxis2': <{{repr}}DomainAxis: size(1)>}

        Select the construct that has the "standard_name" property of 'latitude':

        >>> f.construct('latitude')
        <{{repr}}DimensionCoordinate: latitude(5) degrees_north>

        Select the cell method construct that has a "method" of 'mean':

        >>> f.construct('method:mean')
        <{{repr}}CellMethod: area: mean>

        Attempt to select the construct whose "standard_name" start with the
        letter 'l':

        >>> import re
        >>> f.construct(re.compile('^l'))
        ValueError: Can't return 2 constructs
        >>> f.construct(re.compile('^l'), default='no construct')
        'no construct'

        """
        #        return self._select_construct(
        #            (),
        #            "construct",
        #            identity,
        #            key=False,
        #            default=default,
        #            item=False,
        #            **filter_kwargs,
        #        )

        return self._filter_interface(
            (),
            "construct",
            identity,
            construct=True,
            key=False,
            item=False,
            default=default,
            **filter_kwargs,
        )

    def construct_item(self, *identity, default=ValueError(), **filter_kwargs):
        """Return a metadata construct and its identifier.

        If zero or two or more constructs are selected then an
        exception is raised, or the *default* parameter is returned.

        All constructs that

        .. versionadded:: (cfdm) 1.8.9.0

        .. seealso:: `construct_key`, `constructs`

        :Parameters:

            identity: optional
                Select constructs that have an identity, defined by
                their `!identities` methods, that matches any of the
                given values.

                Additionally, the values are matched against construct
                identifiers, with or without the ``'key%'`` prefix.

                If no values are provided then all constructs are
                selected.

                {{value match}}

                {{displayed identity}}

            default: optional
                Return the value of the *default* parameter if there
                is no unique construct.

                {{default Exception}}

            {{filter_kwargs: optional}}

        :Returns:

            `tuple`
                The selected construct and its construct identifer.

        """
        return self._filter_interface(
            (),
            "construct",
            identity,
            construct=True,
            key=False,
            item=True,
            default=default,
            **filter_kwargs,
        )

    #        return self._select_construct(
    #            (),
    #            "construct",
    #            identity,
    #            key=False,
    #            default=default,
    #            item=True,
    #            **filter_kwargs,
    #        )

    def construct_key(self, *identity, default=ValueError(), **filter_kwargs):
        """Return the identifier of a metadata construct.

        If zero or two or more constructs are selected then an
        exception is raised, or the *default* parameter is returned.

        .. versionadded:: (cfdm) 1.7.0

        .. seealso:: `construct`, `constructs`

        :Parameters:

            identity: optional
                Select constructs that have an identity, defined by
                their `!identities` methods, that matches any of the
                given values.

                Additionally, the values are matched against construct
                identifiers, with or without the ``'key%'`` prefix.

                If no values are provided then all constructs are
                selected.

                {{value match}}

                {{displayed identity}}

            default: optional
                Return the value of the *default* parameter if there
                is no unique construct.

                {{default Exception}}

            {{filter_kwargs: optional}}

        :Returns:

            `str`
                The identifier of the selected construct.

        **Examples:**

        >>> print(f.constructs)
        Constructs:
        {'cellmethod0': <{{repr}}ellMethod: area: mean>,
         'dimensioncoordinate0': <{{repr}}DimensionCoordinate: latitude(5) degrees_north>,
         'dimensioncoordinate1': <{{repr}}DimensionCoordinate: longitude(8) degrees_east>,
         'dimensioncoordinate2': <{{repr}}DimensionCoordinate: long_name=time(1) days since 2018-12-01 >,
         'domainaxis0': <{{repr}}DomainAxis: size(5)>,
         'domainaxis1': <{{repr}}DomainAxis: size(8)>,
         'domainaxis2': <{{repr}}DomainAxis: size(1)>}

        Select the construct that has the "standard_name" property of
        'latitude':

        >>> f.construct_key('latitude')
         'dimensioncoordinate0'

        Select the cell method construct that has a "method" of 'mean':

        >>> f.construct_key('method:mean')
        'cellmethod0'

        Attempt to select the construct whose "standard_name" start with
        the letter 'l':

        >>> import re
        >>> f.construct_key(re.compile('^l'))
        ValueError: Can't return the key of 2 constructs
        >>> f.construct_key(re.compile('^l'), default='no construct')
        'no construct'

        """
        return self._filter_interface(
            (),
            "construct",
            identity,
            construct=True,
            key=True,
            item=False,
            default=default,
            **filter_kwargs,
        )

    #
    #        return self._select_construct(
    #            (),
    #            "construct",
    #            identity,
    #            key=True,
    #            default=default,
    #            item=False,
    #            **filter_kwargs,
    #        )

    def domain_axis_key(
        self, *identity, default=ValueError(), **filter_kwargs
    ):
        """Returns the domain axis key spanned by 1-d coordinates.

        Specifically, returns the key of the domain axis construct that
        is spanned by 1-d coordinate constructs.

        :Parameters:

            identity: optional
                Select the 1-d dimension coordinate constructs that
                have an identity, defined by their `!identities`
                methods, that matches any of the given values.

                If no values are provided then all 1-d dimension
                coordinate constructs are selected.

                {{value match}}

                {{displayed identity}}

            default: optional
                Return the value of the *default* parameter if there
                is no unique construct.

                {{default Exception}}

            {{filter_kwargs: optional}}

        :Returns:

            `str`
                The key of the domain axis construct that is spanned by
                the data of the selected 1-d coordinate constructs.

        **Examples:**

        >>> print(f.constructs())
        Constructs:
        {'dimensioncoordinate0': <{{repr}}DimensionCoordinate: time(1) days since 1964-01-21 00:00:00 >,
         'dimensioncoordinate1': <{{repr}}DimensionCoordinate: pressure(23) mbar>,
         'dimensioncoordinate2': <{{repr}}DimensionCoordinate: latitude(160) degrees_north>,
         'dimensioncoordinate3': <{{repr}}DimensionCoordinate: longitude(320) degrees_east>,
         'domainaxis0': <{{repr}}DomainAxis: size(1)>,
         'domainaxis1': <{{repr}}DomainAxis: size(23)>,
         'domainaxis2': <{{repr}}DomainAxis: size(160)>,
         'domainaxis3': <{{repr}}DomainAxis: size(320)>}
        >>> f.domain.domain_axis_key('time')
        'domainaxis0'
        >>> f.domain.domain_axis_key('longitude')
        'domainaxis3'

        """
        # Select 1-d coordinate constructs with the given identity
        c = self.coordinates(
            *identity,
            filter_by_naxes=(1,),
            todict=True,
        )
        if not c:
            if default is None:
                return default

            return self._default(
                default,
                "There are no 1-d coordinate constructs",
            )

        data_axes = self.constructs.data_axes()
        domain_axes = self.domain_axes(todict=True)

        keys = []
        for ckey, coord in c.items():
            axes = data_axes.get(ckey)
            if axes is None:
                continue

            key = axes[0]
            if key in domain_axes:
                keys.append(key)

        keys = set(keys)

        n = len(keys)
        if n == 1:
            return keys.pop()

        if default is None:
            return default

        if not keys:
            return self._default(
                default,
                "Some selected 1-d coordinate constructs "
                "have not been assigned a domain axis construct",
            )

        return self._default(
            default,
            "The selected 1-d coordinate constructs "
            f"span multiple domain axes: {keys!r}",
        )

    def has_construct(self, *identity, **filter_kwargs):
        """Whether a unique metadata construct exists.

        .. versionadded:: (cfdm) 1.7.0

        .. seealso:: `get_construct`, `constructs`, `has_construct`,
                     `set_construct`

        :Parameters:

            identity:
                Select the unique construct that has the identity,
                defined by its `!identities` method, that matches the
                given values.

                Additionally, the values are matched against construct
                identifiers, with or without the ``'key%'`` prefix.

                {{value match}}

                {{displayed identity}}

                .. versionadded:: (cfdm) 1.8.9.0

            {{filter_kwargs: optional}}

        :Returns:

                The removed metadata construct.

        **Examples:**

        >>> f = {{package}}.example_field(0)
        >>> print(f)
        Field: specific_humidity (ncvar%q)
        ----------------------------------
        Data            : specific_humidity(latitude(5), longitude(8)) 1
        Cell methods    : area: mean
        Dimension coords: latitude(5) = [-75.0, ..., 75.0] degrees_north
                        : longitude(8) = [22.5, ..., 337.5] degrees_east
                        : time(1) = [2019-01-01 00:00:00]
        >>> f.has_construct('time')
        True
        >>> f.del_construct('altitude')
        False

        """
        if (
            len(identity) == 1
            and not filter_kwargs
            and identity[0] in self.constructs
        ):
            # Faster return for when identity is a single construct
            # identifier
            return True

        return bool(
            self.construct(*identity, default=None, **filter_kwargs)
            is not None
        )
