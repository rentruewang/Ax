#!/usr/bin/env python3
# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import dataclasses

from ax.core.arm import Arm
from ax.core.observation import ObservationFeatures
from ax.core.parameter import (
    ChoiceParameter,
    FixedParameter,
    ParameterType,
    RangeParameter,
)
from ax.core.parameter_constraint import (
    OrderConstraint,
    ParameterConstraint,
    SumConstraint,
)
from ax.core.search_space import SearchSpace, SearchSpaceDigest, HierarchicalSearchSpace
from ax.exceptions.core import UserInputError
from ax.utils.common.constants import Keys
from ax.utils.common.testutils import TestCase
from ax.utils.testing.core_stubs import (
    get_model_parameter,
    get_lr_parameter,
    get_l2_reg_weight_parameter,
    get_num_boost_rounds_parameter,
    get_hierarchical_search_space,
)
from ax.utils.testing.core_stubs import get_parameter_constraint

TOTAL_PARAMS = 6
TUNABLE_PARAMS = 4
RANGE_PARAMS = 3


class SearchSpaceTest(TestCase):
    def setUp(self):
        self.a = RangeParameter(
            name="a", parameter_type=ParameterType.FLOAT, lower=0.5, upper=5.5
        )
        self.b = RangeParameter(
            name="b", parameter_type=ParameterType.INT, lower=2, upper=10
        )
        self.c = ChoiceParameter(
            name="c", parameter_type=ParameterType.STRING, values=["foo", "bar", "baz"]
        )
        self.d = FixedParameter(name="d", parameter_type=ParameterType.BOOL, value=True)
        self.e = ChoiceParameter(
            name="e", parameter_type=ParameterType.FLOAT, values=[0.0, 0.1, 0.2, 0.5]
        )
        self.f = RangeParameter(
            name="f",
            parameter_type=ParameterType.INT,
            lower=2,
            upper=10,
            log_scale=True,
        )
        self.g = RangeParameter(
            name="g", parameter_type=ParameterType.FLOAT, lower=0.0, upper=1.0
        )
        self.parameters = [self.a, self.b, self.c, self.d, self.e, self.f]
        self.ss1 = SearchSpace(parameters=self.parameters)
        self.ss2 = SearchSpace(
            parameters=self.parameters,
            parameter_constraints=[
                OrderConstraint(lower_parameter=self.a, upper_parameter=self.b)
            ],
        )
        self.ss1_repr = (
            "SearchSpace("
            "parameters=["
            "RangeParameter(name='a', parameter_type=FLOAT, range=[0.5, 5.5]), "
            "RangeParameter(name='b', parameter_type=INT, range=[2, 10]), "
            "ChoiceParameter(name='c', parameter_type=STRING, "
            "values=['foo', 'bar', 'baz'], is_ordered=False, sort_values=False), "
            "FixedParameter(name='d', parameter_type=BOOL, value=True), "
            "ChoiceParameter(name='e', parameter_type=FLOAT, "
            "values=[0.0, 0.1, 0.2, 0.5], is_ordered=True, sort_values=True), "
            "RangeParameter(name='f', parameter_type=INT, range=[2, 10], "
            "log_scale=True)], "
            "parameter_constraints=[])"
        )
        self.ss2_repr = (
            "SearchSpace("
            "parameters=["
            "RangeParameter(name='a', parameter_type=FLOAT, range=[0.5, 5.5]), "
            "RangeParameter(name='b', parameter_type=INT, range=[2, 10]), "
            "ChoiceParameter(name='c', parameter_type=STRING, "
            "values=['foo', 'bar', 'baz'], is_ordered=False, sort_values=False), "
            "FixedParameter(name='d', parameter_type=BOOL, value=True), "
            "ChoiceParameter(name='e', parameter_type=FLOAT, "
            "values=[0.0, 0.1, 0.2, 0.5], is_ordered=True, sort_values=True), "
            "RangeParameter(name='f', parameter_type=INT, range=[2, 10], "
            "log_scale=True)], "
            "parameter_constraints=[OrderConstraint(a <= b)])"
        )

    def testEq(self):
        ss2 = SearchSpace(
            parameters=self.parameters,
            parameter_constraints=[
                OrderConstraint(lower_parameter=self.a, upper_parameter=self.b)
            ],
        )
        self.assertEqual(self.ss2, ss2)
        self.assertNotEqual(self.ss1, self.ss2)

    def testProperties(self):
        self.assertEqual(len(self.ss1.parameters), TOTAL_PARAMS)
        self.assertTrue("a" in self.ss1.parameters)
        self.assertTrue(len(self.ss1.tunable_parameters), TUNABLE_PARAMS)
        self.assertFalse("d" in self.ss1.tunable_parameters)
        self.assertTrue(len(self.ss1.range_parameters), RANGE_PARAMS)
        self.assertFalse("c" in self.ss1.range_parameters)
        self.assertTrue(len(self.ss1.parameter_constraints) == 0)
        self.assertTrue(len(self.ss2.parameter_constraints) == 1)

    def testRepr(self):
        self.assertEqual(str(self.ss2), self.ss2_repr)
        self.assertEqual(str(self.ss1), self.ss1_repr)

    def testSetter(self):
        new_c = SumConstraint(
            parameters=[self.a, self.b], is_upper_bound=True, bound=10
        )
        self.ss2.add_parameter_constraints([new_c])
        self.assertEqual(len(self.ss2.parameter_constraints), 2)

        self.ss2.set_parameter_constraints([])
        self.assertEqual(len(self.ss2.parameter_constraints), 0)

        update_p = RangeParameter(
            name="b", parameter_type=ParameterType.INT, lower=10, upper=20
        )
        self.ss2.add_parameter(self.g)
        self.assertEqual(len(self.ss2.parameters), TOTAL_PARAMS + 1)

        self.ss2.update_parameter(update_p)
        self.assertEqual(self.ss2.parameters["b"].lower, 10)

    def testBadConstruction(self):
        # Duplicate parameter
        with self.assertRaises(ValueError):
            p1 = self.parameters + [self.parameters[0]]
            SearchSpace(parameters=p1, parameter_constraints=[])

        # Constraint on non-existent parameter
        with self.assertRaises(ValueError):
            SearchSpace(
                parameters=self.parameters,
                parameter_constraints=[
                    OrderConstraint(lower_parameter=self.a, upper_parameter=self.g)
                ],
            )

        # Vanilla Constraint on non-existent parameter
        with self.assertRaises(ValueError):
            SearchSpace(
                parameters=self.parameters,
                parameter_constraints=[
                    ParameterConstraint(constraint_dict={"g": 1}, bound=0)
                ],
            )

        # Constraint on non-numeric parameter
        with self.assertRaises(ValueError):
            SearchSpace(
                parameters=self.parameters,
                parameter_constraints=[
                    OrderConstraint(lower_parameter=self.a, upper_parameter=self.d)
                ],
            )

        # Constraint on choice parameter
        with self.assertRaises(ValueError):
            SearchSpace(
                parameters=self.parameters,
                parameter_constraints=[
                    OrderConstraint(lower_parameter=self.a, upper_parameter=self.e)
                ],
            )

        # Constraint on logscale parameter
        with self.assertRaises(ValueError):
            SearchSpace(
                parameters=self.parameters,
                parameter_constraints=[
                    OrderConstraint(lower_parameter=self.a, upper_parameter=self.f)
                ],
            )

        # Constraint on mismatched parameter
        with self.assertRaises(ValueError):
            wrong_a = self.a.clone()
            wrong_a.update_range(upper=10)
            SearchSpace(
                parameters=self.parameters,
                parameter_constraints=[
                    OrderConstraint(lower_parameter=wrong_a, upper_parameter=self.b)
                ],
            )

    def testBadSetter(self):
        new_p = RangeParameter(
            name="b", parameter_type=ParameterType.FLOAT, lower=0.0, upper=1.0
        )

        # Add duplicate parameter
        with self.assertRaises(ValueError):
            self.ss1.add_parameter(new_p)

        # Update parameter to different type
        with self.assertRaises(ValueError):
            self.ss1.update_parameter(new_p)

        # Update non-existent parameter
        new_p = RangeParameter(
            name="g", parameter_type=ParameterType.FLOAT, lower=0.0, upper=1.0
        )
        with self.assertRaises(ValueError):
            self.ss1.update_parameter(new_p)

    def testCheckMembership(self):
        p_dict = {"a": 1.0, "b": 5, "c": "foo", "d": True, "e": 0.2, "f": 5}

        # Valid
        self.assertTrue(self.ss2.check_membership(p_dict))

        # Value out of range
        p_dict["a"] = 20.0
        self.assertFalse(self.ss2.check_membership(p_dict))
        with self.assertRaises(ValueError):
            self.ss2.check_membership(p_dict, raise_error=True)

        # Violate constraints
        p_dict["a"] = 5.3
        self.assertFalse(self.ss2.check_membership(p_dict))
        with self.assertRaises(ValueError):
            self.ss2.check_membership(p_dict, raise_error=True)

        # Incomplete param dict
        p_dict.pop("a")
        self.assertFalse(self.ss2.check_membership(p_dict))
        with self.assertRaises(ValueError):
            self.ss2.check_membership(p_dict, raise_error=True)

        # Unknown parameter
        p_dict["q"] = 40
        self.assertFalse(self.ss2.check_membership(p_dict))
        with self.assertRaises(ValueError):
            self.ss2.check_membership(p_dict, raise_error=True)

    def testCheckTypes(self):
        p_dict = {"a": 1.0, "b": 5, "c": "foo", "d": True, "e": 0.2, "f": 5}

        # Valid
        self.assertTrue(self.ss2.check_types(p_dict))

        # Invalid type
        p_dict["b"] = 5.2
        self.assertFalse(self.ss2.check_types(p_dict))
        with self.assertRaises(ValueError):
            self.ss2.check_types(p_dict, raise_error=True)
        p_dict["b"] = 5

        # Unknown parameter
        p_dict["q"] = 40
        self.assertFalse(self.ss2.check_types(p_dict))
        with self.assertRaises(ValueError):
            self.ss2.check_types(p_dict, raise_error=True)

    def testCastArm(self):
        p_dict = {"a": 1.0, "b": 5.0, "c": "foo", "d": True, "e": 0.2, "f": 5}

        # Check "b" parameter goes from float to int
        self.assertTrue(isinstance(p_dict["b"], float))
        new_arm = self.ss2.cast_arm(Arm(p_dict))
        self.assertTrue(isinstance(new_arm.parameters["b"], int))

        # Unknown parameter should be unchanged
        p_dict["q"] = 40
        new_arm = self.ss2.cast_arm(Arm(p_dict))
        self.assertTrue(isinstance(new_arm.parameters["q"], int))

    def testCopy(self):
        a = RangeParameter("a", ParameterType.FLOAT, 1.0, 5.5)
        b = RangeParameter("b", ParameterType.FLOAT, 2.0, 5.5)
        c = ChoiceParameter("c", ParameterType.INT, [2, 3])
        ss = SearchSpace(
            parameters=[a, b, c],
            parameter_constraints=[
                OrderConstraint(lower_parameter=a, upper_parameter=b)
            ],
        )
        ss_copy = ss.clone()
        self.assertEqual(len(ss_copy.parameters), len(ss_copy.parameters))
        self.assertEqual(
            len(ss_copy.parameter_constraints), len(ss_copy.parameter_constraints)
        )

        ss_copy.add_parameter(FixedParameter("d", ParameterType.STRING, "h"))
        self.assertNotEqual(len(ss_copy.parameters), len(ss.parameters))

    def testOutOfDesignArm(self):
        arm1 = self.ss1.out_of_design_arm()
        arm2 = self.ss2.out_of_design_arm()
        arm1_nones = [p is None for p in arm1.parameters.values()]
        self.assertTrue(all(arm1_nones))
        self.assertTrue(arm1 == arm2)

    def testConstructArm(self):
        # Test constructing an arm of default values
        arm = self.ss1.construct_arm(name="test")
        self.assertEqual(arm.name, "test")
        for p_name in self.ss1.parameters.keys():
            self.assertTrue(p_name in arm.parameters)
            self.assertEqual(arm.parameters[p_name], None)

        # Test constructing an arm with a custom value
        arm = self.ss1.construct_arm({"a": 1.0})
        for p_name in self.ss1.parameters.keys():
            self.assertTrue(p_name in arm.parameters)
            if p_name == "a":
                self.assertEqual(arm.parameters[p_name], 1.0)
            else:
                self.assertEqual(arm.parameters[p_name], None)

        # Test constructing an arm with a bad param name
        with self.assertRaises(ValueError):
            self.ss1.construct_arm({"IDONTEXIST_a": 1.0})

        # Test constructing an arm with a bad param name
        with self.assertRaises(ValueError):
            self.ss1.construct_arm({"a": "notafloat"})


class SearchSpaceDigestTest(TestCase):
    def setUp(self):
        self.kwargs = {
            "feature_names": ["a", "b", "c"],
            "bounds": [(0.0, 1.0), (0, 2), (0, 4)],
            "ordinal_features": [1],
            "categorical_features": [2],
            "discrete_choices": {1: [0, 1, 2], 2: [0, 0.25, 4.0]},
            "task_features": [3],
            "fidelity_features": [0],
            "target_fidelities": {0: 1.0},
        }

    def testSearchSpaceDigest(self):
        # test required fields
        with self.assertRaises(TypeError):
            SearchSpaceDigest(bounds=[])
        with self.assertRaises(TypeError):
            SearchSpaceDigest(feature_names=[])
        # test instantiation
        ssd = SearchSpaceDigest(**self.kwargs)
        self.assertEqual(dataclasses.asdict(ssd), self.kwargs)
        # test default instatiation
        for arg in self.kwargs:
            if arg in {"feature_names", "bounds"}:
                continue
            ssd = SearchSpaceDigest(
                **{k: v for k, v in self.kwargs.items() if k != arg}
            )


class HierarchicalSearchSpaceTest(TestCase):
    def setUp(self):
        self.model_parameter = get_model_parameter()
        self.lr_parameter = get_lr_parameter()
        self.l2_reg_weight_parameter = get_l2_reg_weight_parameter()
        self.num_boost_rounds_parameter = get_num_boost_rounds_parameter()
        self.hss_1 = get_hierarchical_search_space()
        self.use_linear_parameter = ChoiceParameter(
            name="use_linear",  # Contrived!
            parameter_type=ParameterType.BOOL,
            values=[True, False],
            dependents={
                True: ["model"],
            },
        )
        self.hss_2 = HierarchicalSearchSpace(
            parameters=[
                self.use_linear_parameter,
                self.model_parameter,
                self.lr_parameter,
                self.l2_reg_weight_parameter,
                self.num_boost_rounds_parameter,
            ]
        )
        self.model_2_parameter = ChoiceParameter(
            name="model_2",
            parameter_type=ParameterType.STRING,
            values=["Linear", "XGBoost"],
            dependents={
                "Linear": ["learning_rate", "l2_reg_weight"],
                "XGBoost": ["num_boost_rounds"],
            },
        )
        self.hss_with_constraints = HierarchicalSearchSpace(
            parameters=[
                self.model_parameter,
                self.lr_parameter,
                self.l2_reg_weight_parameter,
                self.num_boost_rounds_parameter,
            ],
            parameter_constraints=[
                get_parameter_constraint(
                    param_x=self.lr_parameter.name,
                    param_y=self.l2_reg_weight_parameter.name,
                ),
            ],
        )
        self.hss_1_arm_1_flat = Arm(
            parameters={
                "model": "Linear",
                "learning_rate": 0.01,
                "l2_reg_weight": 0.0001,
                "num_boost_rounds": 12,
            }
        )
        self.hss_1_arm_2_flat = Arm(
            parameters={
                "model": "XGBoost",
                "learning_rate": 0.01,
                "l2_reg_weight": 0.0001,
                "num_boost_rounds": 12,
            }
        )
        self.hss_1_arm_missing_param = Arm(
            parameters={
                "model": "Linear",
                "l2_reg_weight": 0.0001,
                "num_boost_rounds": 12,
            }
        )
        self.hss_1_arm_1_cast = Arm(
            parameters={
                "model": "Linear",
                "learning_rate": 0.01,
                "l2_reg_weight": 0.0001,
            }
        )
        self.hss_1_arm_2_cast = Arm(
            parameters={
                "model": "XGBoost",
                "num_boost_rounds": 12,
            }
        )

    def test_init(self):
        self.assertEqual(self.hss_1._root, self.model_parameter)
        self.assertEqual(
            self.hss_1._all_parameter_names,
            {"l2_reg_weight", "learning_rate", "num_boost_rounds", "model"},
        )
        self.assertEqual(self.hss_2._root, self.use_linear_parameter)
        self.assertEqual(
            self.hss_2._all_parameter_names,
            {
                "l2_reg_weight",
                "learning_rate",
                "num_boost_rounds",
                "model",
                "use_linear",
            },
        )

    def test_validation(self):
        # Case where dependent parameter is not in the search space.
        with self.assertRaisesRegex(ValueError, ".* 'l2_reg_weight' is not part"):
            HierarchicalSearchSpace(
                parameters=[
                    ChoiceParameter(
                        name="model",
                        parameter_type=ParameterType.STRING,
                        values=["Linear", "XGBoost"],
                        dependents={
                            "Linear": ["learning_rate", "l2_reg_weight"],
                            "XGBoost": ["num_boost_rounds"],
                        },
                    ),
                    self.lr_parameter,
                    self.num_boost_rounds_parameter,
                ]
            )

        # Case where there are two root-parameter candidates.
        with self.assertRaisesRegex(NotImplementedError, "Could not find the root"):
            HierarchicalSearchSpace(
                parameters=[
                    self.model_parameter,
                    self.model_2_parameter,
                    self.lr_parameter,
                    self.l2_reg_weight_parameter,
                    self.num_boost_rounds_parameter,
                ]
            )

        # TODO: Test case where subtrees are not independent.
        with self.assertRaisesRegex(UserInputError, ".* contain the same parameters"):
            HierarchicalSearchSpace(
                parameters=[
                    ChoiceParameter(
                        name="root",
                        parameter_type=ParameterType.BOOL,
                        values=[True, False],
                        dependents={
                            True: ["model", "model_2"],
                        },
                    ),
                    self.model_parameter,
                    self.model_2_parameter,
                    self.lr_parameter,
                    self.l2_reg_weight_parameter,
                    self.num_boost_rounds_parameter,
                ]
            )

    def test_hierarchical_structure_str(self):
        self.assertEqual(
            self.hss_1.hierarchical_structure_str(),
            f"{self.hss_1.root}\n\t(Linear)\n\t\t{self.lr_parameter}\n\t\t"
            f"{self.l2_reg_weight_parameter}\n\t(XGBoost)\n\t\t"
            f"{self.num_boost_rounds_parameter}\n",
        )
        self.assertEqual(
            self.hss_1.hierarchical_structure_str(parameter_names_only=True),
            f"{self.hss_1.root.name}\n\t(Linear)\n\t\t{self.lr_parameter.name}"
            f"\n\t\t{self.l2_reg_weight_parameter.name}\n\t(XGBoost)\n\t\t"
            f"{self.num_boost_rounds_parameter.name}\n",
        )

    def test_flatten(self):
        # Test on basic HSS.
        flattened_hss_1 = self.hss_1.flatten()
        self.assertIsNot(flattened_hss_1, self.hss_1)
        self.assertEqual(type(flattened_hss_1), SearchSpace)
        self.assertFalse(isinstance(flattened_hss_1, HierarchicalSearchSpace))
        self.assertEqual(flattened_hss_1.parameters, self.hss_1.parameters)
        self.assertEqual(
            flattened_hss_1.parameter_constraints, self.hss_1.parameter_constraints
        )
        self.assertTrue(str(self.hss_1).startswith("HierarchicalSearchSpace"))
        self.assertTrue(str(flattened_hss_1).startswith("SearchSpace"))

        # Test on HSS with constraints.
        flattened_hss_with_constraints = self.hss_with_constraints.flatten()
        self.assertIsNot(flattened_hss_with_constraints, self.hss_with_constraints)
        self.assertEqual(type(flattened_hss_with_constraints), SearchSpace)
        self.assertFalse(
            isinstance(flattened_hss_with_constraints, HierarchicalSearchSpace)
        )
        self.assertEqual(
            flattened_hss_with_constraints.parameters,
            self.hss_with_constraints.parameters,
        )
        self.assertEqual(
            flattened_hss_with_constraints.parameter_constraints,
            self.hss_with_constraints.parameter_constraints,
        )
        self.assertTrue(
            str(self.hss_with_constraints).startswith("HierarchicalSearchSpace")
        )
        self.assertTrue(str(flattened_hss_with_constraints).startswith("SearchSpace"))

    def test_cast_arm(self):
        self.assertEqual(  # Check one subtree.
            self.hss_1._cast_arm(arm=self.hss_1_arm_1_flat),
            self.hss_1_arm_1_cast,
        )
        self.assertEqual(  # Check other subtree.
            self.hss_1._cast_arm(arm=self.hss_1_arm_2_flat),
            self.hss_1_arm_2_cast,
        )
        self.assertEqual(  # Check already-cast case.
            self.hss_1._cast_arm(arm=self.hss_1_arm_1_cast),
            self.hss_1_arm_1_cast,
        )
        with self.assertRaises(RuntimeError):
            self.hss_1._cast_arm(arm=self.hss_1_arm_missing_param)

    def test_cast_observation_features(self):
        # Ensure that during casting, full parameterization is saved
        # in metadata and actual parameterization is cast to HSS.
        hss_1_obs_feats_1 = ObservationFeatures.from_arm(arm=self.hss_1_arm_1_flat)
        hss_1_obs_feats_1_cast = self.hss_1.cast_observation_features(
            observation_features=hss_1_obs_feats_1
        )
        self.assertEqual(  # Check one subtree.
            hss_1_obs_feats_1_cast.parameters,
            ObservationFeatures.from_arm(arm=self.hss_1_arm_1_cast).parameters,
        )
        self.assertEqual(  # Check one subtree.
            hss_1_obs_feats_1_cast.metadata.get(Keys.FULL_PARAMETERIZATION),
            hss_1_obs_feats_1.parameters,
        )
        # Check that difference with observation features made from cast arm
        # is only in metadata (to ensure only parameters and metadata are
        # manipulated during casting).
        hss_1_obs_feats_1_cast.metadata = None
        self.assertEqual(
            hss_1_obs_feats_1_cast,
            ObservationFeatures.from_arm(arm=self.hss_1_arm_1_cast),
        )

    def test_flatten_observation_features(self):
        # Ensure that during casting, full parameterization is saved
        # in metadata and actual parameterization is cast to HSS; during
        # flattening, parameterization in metadata is used ot inject back
        # the parameters removed during casting.
        hss_1_obs_feats_1 = ObservationFeatures.from_arm(arm=self.hss_1_arm_1_flat)
        hss_1_obs_feats_1_cast = self.hss_1.cast_observation_features(
            observation_features=hss_1_obs_feats_1
        )
        hss_1_obs_feats_1_flattened = self.hss_1.flatten_observation_features(
            observation_features=hss_1_obs_feats_1_cast
        )
        self.assertEqual(  # Cast-flatten roundtrip.
            hss_1_obs_feats_1.parameters,
            hss_1_obs_feats_1_flattened.parameters,
        )
        self.assertEqual(  # Check that both cast and flattened have full params.
            hss_1_obs_feats_1_cast.metadata.get(Keys.FULL_PARAMETERIZATION),
            hss_1_obs_feats_1_flattened.metadata.get(Keys.FULL_PARAMETERIZATION),
        )
        # Check that flattening observation features without metadata does nothing.
        self.assertEqual(
            self.hss_1.flatten_observation_features(
                observation_features=hss_1_obs_feats_1
            ),
            hss_1_obs_feats_1,
        )
