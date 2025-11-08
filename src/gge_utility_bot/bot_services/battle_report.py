import io

import numpy as np
from PIL import Image
from typing_extensions import Sequence, TypedDict


class AlignmentData(TypedDict):
    x: int
    y: int
    scale: float


class CornerData(TypedDict):
    x: int
    y: int
    width: int
    height: int


class SummaryResult(TypedDict):
    summary_image: np.ndarray


class Aligner:
    VICTORY_BANNER_COLOR = (239, 177, 24)
    DEFEAT_BANNER_COLOR = (193, 61, 10)
    COLOR_TOLERANCE = 4

    SAMPLE_BANNER_WIDTH = 273
    SAMPLE_BANNER_HEIGHT = 41
    BANNER_RATIO = SAMPLE_BANNER_WIDTH / SAMPLE_BANNER_HEIGHT
    RATIO_TOLERANCE = 0.1  # 10%

    @classmethod
    def align(
        cls,
        input_img_arr: np.ndarray,
    ) -> AlignmentData | None:
        """
        Generate data for aligning the input image.

        :param input_img_arr: Input image as an array
        :type input_img_arr: np.ndarray
        :return: Data for alignment
        :rtype: AlignmentData | None
        """
        banner_mask = cls._get_banner_mask(input_img_arr)
        x_shifted, y_shifted = cls._shift_banner_mask(banner_mask)

        # Find pixels where on their right / bottom is a banner pixel
        # while themselves are not.
        x_enter = (~banner_mask) & x_shifted
        y_enter = (~banner_mask) & y_shifted

        corners = np.argwhere(
            banner_mask & (~x_shifted) & (~y_shifted),
        )

        corner_data = cls._find_best_corner(
            list(corners), x_enter, y_enter,
        )
        if corner_data is None:
            return None

        # Using width because it's larger, lower relative error
        scale = corner_data["width"] / cls.SAMPLE_BANNER_WIDTH

        return {
            "x": corner_data["x"],
            "y": corner_data["y"],
            "scale": scale,
        }

    @classmethod
    def _find_best_corner(
        cls,
        corners: Sequence[tuple[int, int]],
        x_enter: np.ndarray,
        y_enter: np.ndarray,
    ) -> CornerData | None:
        """
        Find the corner that is most likely the bottom-right corner
        of the banner.

        :param corners: A sequence of corner coordinates
        :type corners: Sequence[tuple[int, int]]
        :param x_enter: An array showing all "entries" from non-banner
            pixels to banner pixels horizontally
        :type x_enter: np.ndarray
        :param y_enter: An array showing all "entries" from non-banner
            pixels to banner pixels vertically
        :type y_enter: np.ndarray
        :return: The position of the corner with the highest score
            and the predicted scale of the image relative to the
            sample.
        :rtype: CornerData | None
        """
        # Select banner corner
        dims_data: list[tuple[int, int, int, int]] = []
        for y, x in corners:
            # Get all pos that have the same x / y to the corner
            x_enter_positions = np.nonzero(x_enter[y, :])[0]
            y_enter_positions = np.nonzero(y_enter[:, x])[0]

            # Find the nearest x pos west of the corner
            x_enter_pos = np.max(
                x_enter_positions[x_enter_positions < x],
                initial=0,
            )
            # Find the nearest y pos north of the corner
            y_enter_pos = np.max(
                y_enter_positions[y_enter_positions < y],
                initial=0,
            )

            width = x - int(x_enter_pos)
            height = y - int(y_enter_pos)
            dims_data.append((x, y, width, height))

        # Find the most likely correct corner
        corner_x, corner_y, w, h = min(
            dims_data,
            key=lambda data: abs(
                data[2] / data[3] - cls.BANNER_RATIO,
            )
        )

        ratio = w / h
        # No match if the ratio exceeds tolerance
        if abs(ratio / cls.BANNER_RATIO - 1) > cls.RATIO_TOLERANCE:
            return None

        return {
            "x": corner_x,
            "y": corner_y,
            "width": w,
            "height": h,
        }

    @classmethod
    def _get_banner_mask(
        cls,
        input_img_arr: np.ndarray,
    ) -> np.ndarray:
        """
        Find all pixels that have similar color values to banners.

        :param input_img_arr: Input image as an array
        :type input_img_arr: np.ndarray
        :return: A numpy array where pixels with similar color 
            values are True, False otherwise
        :rtype: np.ndarray
        """
        victory_diff = (
            input_img_arr
            - np.array(cls.VICTORY_BANNER_COLOR)[None, None, :]
        ) % 256
        defeat_diff = (
            input_img_arr
            - np.array(cls.DEFEAT_BANNER_COLOR)[None, None, :]
        ) % 256

        is_victory_banner = np.all(
            (victory_diff <= cls.COLOR_TOLERANCE)
            | (victory_diff >= 256 - cls.COLOR_TOLERANCE),
            axis=2,
        )
        is_defeat_banner = np.all(
            (defeat_diff <= cls.COLOR_TOLERANCE)
            | (defeat_diff >= 256 - cls.COLOR_TOLERANCE),
            axis=2,
        )
        return is_victory_banner | is_defeat_banner

    @classmethod
    def _shift_banner_mask(
        cls,
        banner_mask: np.ndarray,
    ) -> tuple[np.ndarray, np.ndarray]:
        x_shifted = np.zeros_like(banner_mask)
        x_shifted[:, :-1] = banner_mask[:, 1:]
        y_shifted = np.zeros_like(banner_mask)
        y_shifted[:-1, :] = banner_mask[1:, :]

        return x_shifted, y_shifted


class Summarizer:
    OFFSETS = np.array([
        [-511, 43], [-435, 61],  # Date text
        [-491, 67], [-455, 80],  # Time text
        [-533, -44], [-413, 109],  # Info
        [-526, 363], [-391, 465],  # Left player
        [-197, 363], [-62, 465],  # Right player
    ])

    @classmethod
    def generate_summary(
        cls,
        input_img_arr: np.ndarray,
        align_x: int,
        align_y: int,
        scale: float,
    ) -> SummaryResult:
        """
        Generates a summary of the battle report.

        :param input_img_arr: An image of the battle report as
            an numpy array
        :type input_img_arr: np.ndarray
        :param align_x: The x position of the bottom-right corner of
            the banner, used for alignment
        :type align_x: int
        :param align_y: The y position of the bottom-right corner of
            the banner, used for alignment
        :type align_y: int
        :param scale: The scale of the battle report relative to
            the sample.
        :type scale: float
        :return: A summary of the battle report
        :rtype: SummaryResult
        """
        box_pos_array = np.array(
            cls.OFFSETS * scale + [align_x, align_y],
            dtype=np.int16,
        )
        # Prevents negative index
        box_pos_array = np.where(box_pos_array > 0, box_pos_array, 0)
        (
            (date_x1, date_y1), (date_x2, date_y2),
            (time_x1, time_y1), (time_x2, time_y2),
            (info_x1, info_y1), (info_x2, info_y2),
            (left_x1, left_y1), (left_x2, left_y2),
            (right_x1, right_y1), (right_x2, right_y2),
        ) = box_pos_array

        # Get regions
        # These may be used in the future for additional features
        date_img = input_img_arr[date_y1:date_y2, date_x1:date_x2]
        time_img = input_img_arr[time_y1:time_y2, time_x1:time_x2]

        info_img = input_img_arr[info_y1:info_y2, info_x1:info_x2]
        left_img = input_img_arr[left_y1:left_y2, left_x1:left_x2]
        right_img = input_img_arr[
            right_y1:right_y2, right_x1:right_x2,
        ]

        banner_color = tuple(input_img_arr[align_y, align_x])

        summary_img = cls._combine_imgs(
            left_img=left_img,
            middle_img=info_img,
            right_img=right_img,
            bg_color=banner_color,
        )

        return {
            "summary_image": summary_img,
        }

    @classmethod
    def _combine_imgs(
        cls,
        left_img: np.ndarray,
        middle_img: np.ndarray,
        right_img: np.ndarray,
        bg_color: tuple[int, int, int],
    ) -> np.ndarray:
        """
        Horizontally combine 3 images into 1, the specified background
        color will be used to fill in empty space.

        :param info_img: The image at the middle
        :type info_img: np.ndarray
        :param left_img: The image at the left
        :type left_img: np.ndarray
        :param right_img: The image at the right
        :type right_img: np.ndarray
        :param bg_color: The color that will be used to fill empty
            space when combining the images
        :type bg_color: tuple[int, int, int]
        :return: The result of combining the images
        :rtype: np.ndarray
        """
        out_img_shape = (
            max(
                middle_img.shape[0],
                left_img.shape[0],
                right_img.shape[0],
            ),
            (
                middle_img.shape[1]
                + left_img.shape[1]
                + right_img.shape[1]
            ),
            3,
        )
        out_img = np.full(out_img_shape, bg_color, dtype=np.uint8)
        x1 = 0
        for img_arr in [left_img, middle_img, right_img]:
            x2 = x1 + img_arr.shape[1]
            y1 = int((out_img_shape[0] - img_arr.shape[0]) / 2)
            y2 = y1 + img_arr.shape[0]
            out_img[y1:y2, x1:x2, :] = img_arr
            x1 = x2

        return out_img


def summarize(img_buffer: io.BytesIO) -> io.BytesIO | None:
    """
    Generate a summary of a battle report.

    :param img_buffer: A buffer containing image data of the 
        battle report
    :type img_buffer: io.BytesIO
    :return: A buffer containing image data of the summary if
        the input image is a valid battle report, None otherwise
    :rtype: io.BytesIO | None
    """
    img = Image.open(img_buffer)
    rgb_img = img.convert("RGB")
    np_img = np.array(rgb_img)

    alignment_data = Aligner.align(np_img)
    if alignment_data is None:
        return None

    summary_result = Summarizer.generate_summary(
        input_img_arr=np_img,
        align_x=alignment_data["x"],
        align_y=alignment_data["y"],
        scale=alignment_data["scale"],
    )
    summary_img_arr = summary_result["summary_image"]

    # Save image to buffer
    summary_img = Image.fromarray(summary_img_arr)
    summary_img_buffer = io.BytesIO()
    summary_img.save(summary_img_buffer, format="PNG")

    # Move pointer back to the start
    summary_img_buffer.seek(0)
    return summary_img_buffer
