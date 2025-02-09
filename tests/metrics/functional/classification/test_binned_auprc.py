# Copyright (c) Meta Platforms, Inc. and affiliates.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.

import unittest
from typing import Tuple, Union

import torch
from torcheval.metrics.functional.classification.auprc import binary_auprc
from torcheval.metrics.functional.classification.binned_auprc import binary_binned_auprc
from torcheval.utils import random_data as rd


class TestBinaryBinnedAUPRC(unittest.TestCase):
    def _test_binary_binned_auprc_with_input(
        self,
        input: torch.Tensor,
        target: torch.Tensor,
        num_tasks: int,
        threshold: Union[torch.Tensor, int],
        compute_result: Tuple[torch.Tensor, torch.Tensor],
    ) -> None:
        my_compute_result = binary_binned_auprc(
            input,
            target,
            num_tasks=num_tasks,
            threshold=threshold,
        )
        torch.testing.assert_close(
            my_compute_result,
            compute_result,
            equal_nan=True,
            atol=1e-8,
            rtol=1e-5,
        )

        # Also test for cuda
        if torch.cuda.is_available():
            threshold_cuda = (
                threshold.to("cuda")
                if isinstance(threshold, torch.Tensor)
                else threshold
            )
            compute_result_cuda = tuple(c.to("cuda") for c in compute_result)
            my_compute_result = binary_binned_auprc(
                input.to("cuda"),
                target.to("cuda"),
                threshold=threshold_cuda,
            )
            my_compute_result_cuda = tuple(c.to("cuda") for c in my_compute_result)
            torch.testing.assert_close(
                my_compute_result_cuda,
                compute_result_cuda,
                equal_nan=True,
                atol=1e-8,
                rtol=1e-5,
            )

    def test_with_randomized_data_getter(self) -> None:
        num_bins = 5
        num_tasks = 2
        batch_size = 4
        num_updates = 1

        for _ in range(100):
            input, target, threshold = rd.get_rand_inputs_binned_binary(
                num_updates, num_tasks, batch_size, num_bins
            )
            input = input.reshape(shape=(num_tasks, batch_size))
            target = target.reshape(shape=(num_tasks, batch_size))

            input_positions = torch.searchsorted(
                threshold, input, right=False
            )  # get thresholds not larger than each element
            inputs_quantized = threshold[input_positions]

            compute_result = (
                binary_auprc(inputs_quantized, target, num_tasks=num_tasks),
                threshold,
            )
            self._test_binary_binned_auprc_with_input(
                input, target, num_tasks, threshold, compute_result
            )

    def test_single_task_threshold_specified_as_tensor(self) -> None:
        input = torch.tensor([0.2, 0.3, 0.4, 0.5])
        target = torch.tensor([0, 0, 1, 1])
        threshold = torch.tensor([0.0000, 0.2500, 0.7500, 1.0000])
        num_tasks = 1
        compute_result = (
            torch.tensor(2 / 3),
            torch.tensor([0.0000, 0.2500, 0.7500, 1.0000]),
        )
        self._test_binary_binned_auprc_with_input(
            input, target, num_tasks, threshold, compute_result
        )

    def test_single_task_threshold_specified_as_int(self) -> None:
        input = torch.tensor([0.2, 0.8, 0.5, 0.9])
        target = torch.tensor([0, 1, 0, 1])
        threshold = 5
        num_tasks = 1
        compute_result = (
            torch.tensor(1.0),
            torch.tensor([0.0000, 0.2500, 0.5000, 0.7500, 1.0000]),
        )
        self._test_binary_binned_auprc_with_input(
            input, target, num_tasks, threshold, compute_result
        )

    def test_single_task_target_all_zero(self) -> None:
        # See N3224103 for this example
        input = torch.tensor([0.2539, 0.4058, 0.9785, 0.6885])
        target = torch.tensor([0, 0, 0, 0])
        threshold = torch.tensor([0.0000, 0.1183, 0.1195, 0.3587, 1.0000])
        num_tasks = 1
        compute_result = (torch.tensor(0.0), threshold)
        self._test_binary_binned_auprc_with_input(
            input, target, num_tasks, threshold, compute_result
        )

    def test_two_tasks_threshold_specified_as_tensor(self) -> None:
        input = torch.tensor([[0.2, 0.3, 0.4, 0.5], [0, 1, 2, 3]])
        target = torch.tensor([[0, 0, 1, 1], [0, 1, 1, 1]])
        threshold = torch.tensor([0.0000, 0.2500, 0.7500, 1.0000])

        num_tasks = 2
        compute_result = (
            torch.tensor([2 / 3, 1.0000]),
            torch.tensor([0.0000, 0.2500, 0.7500, 1.0000]),
        )
        self._test_binary_binned_auprc_with_input(
            input, target, num_tasks, threshold, compute_result
        )

    def test_binary_binned_auprc_invalid_input(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "`num_tasks` has to be at least 1.",
        ):
            binary_binned_auprc(torch.rand(3, 2), torch.rand(3, 2), num_tasks=-1)

        with self.assertRaisesRegex(
            ValueError,
            "The `input` and `target` should have the same shape, "
            r"got shapes torch.Size\(\[4\]\) and torch.Size\(\[3\]\).",
        ):
            binary_binned_auprc(torch.rand(4), torch.rand(3))

        with self.assertRaisesRegex(
            ValueError,
            "`num_tasks = 1`, `input` and `target` are expected to be one-dimensional tensors or 1xN tensors, but got shape input: "
            r"torch.Size\(\[4, 5\]\), target: torch.Size\(\[4, 5\]\).",
        ):
            binary_binned_auprc(torch.rand(4, 5), torch.rand(4, 5))

        with self.assertRaisesRegex(
            ValueError,
            "`num_tasks = 1`, `input` and `target` are expected to be one-dimensional tensors or 1xN tensors, but got shape input: "
            r"torch.Size\(\[4, 5, 5\]\), target: torch.Size\(\[4, 5, 5\]\).",
        ):
            binary_binned_auprc(torch.rand(4, 5, 5), torch.rand(4, 5, 5))

        with self.assertRaisesRegex(
            ValueError, "The `threshold` should be a sorted tensor."
        ):
            binary_binned_auprc(
                torch.rand(4),
                torch.rand(4),
                threshold=torch.tensor([0.1, 0.2, 0.5, 0.7, 0.6]),
            )

        with self.assertRaisesRegex(
            ValueError,
            r"The values in `threshold` should be in the range of \[0, 1\].",
        ):
            binary_binned_auprc(
                torch.rand(4),
                torch.rand(4),
                threshold=torch.tensor([-0.1, 0.2, 0.5, 0.7]),
            )

        with self.assertRaisesRegex(
            ValueError,
            r"`threshold` should be 1-dimensional, but got 2D tensor.",
        ):
            binary_binned_auprc(
                torch.rand(4),
                torch.rand(4),
                threshold=torch.tensor([[-0.1, 0.2, 0.5, 0.7], [0.0, 0.4, 0.6, 1.0]]),
            )

        with self.assertRaisesRegex(
            ValueError,
            r"First value in `threshold` should be 0.",
        ):
            binary_binned_auprc(
                torch.rand(4),
                torch.rand(4),
                threshold=torch.tensor([0.1, 0.2, 0.5, 1.0]),
            )

        with self.assertRaisesRegex(
            ValueError,
            r"Last value in `threshold` should be 1.",
        ):
            binary_binned_auprc(
                torch.rand(4),
                torch.rand(4),
                threshold=torch.tensor([0.0, 0.2, 0.5, 0.9]),
            )
