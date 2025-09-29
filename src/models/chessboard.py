import cv2
import numpy as np

from typing import (Any, ClassVar, Dict, Final, List, Mapping, Optional,
                    Sequence, Tuple)

from typing_extensions import Self
from viam.components.camera import Camera
from viam.components.pose_tracker import *
from viam.media.utils.pil import viam_to_pil_image
from viam.media.video import CameraMimeType
from viam.proto.app.robot import ComponentConfig
from viam.proto.common import Geometry, Pose, PoseInFrame, ResourceName
from viam.resource.base import ResourceBase
from viam.resource.easy_resource import EasyResource
from viam.resource.types import Model, ModelFamily
from viam.utils import struct_to_dict, ValueTypes

from ..utils.utils import call_go_ov2mat, call_go_mat2ov


# required attributes
cam_attr = "camera_name"
pattern_attr = "pattern_size"
square_attr = "square_size_mm"


class Chessboard(PoseTracker, EasyResource):
    # To enable debug-level logging, either run viam-server with the --debug option,
    # or configure your resource/machine to display debug logs.
    MODEL: ClassVar[Model] = Model(ModelFamily("viam", "opencv"), "chessboard")

    @classmethod
    def new(
        cls, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ) -> Self:
        """This method creates a new instance of this PoseTracker component.
        The default implementation sets the name from the `config` parameter and then calls `reconfigure`.

        Args:
            config (ComponentConfig): The configuration for this resource
            dependencies (Mapping[ResourceName, ResourceBase]): The dependencies (both required and optional)

        Returns:
            Self: The resource
        """
        return super().new(config, dependencies)

    @classmethod
    def validate_config(
        cls, config: ComponentConfig
    ) -> Tuple[Sequence[str], Sequence[str]]:
        """This method allows you to validate the configuration object received from the machine,
        as well as to return any required dependencies or optional dependencies based on that `config`.

        Args:
            config (ComponentConfig): The configuration for this resource

        Returns:
            Tuple[Sequence[str], Sequence[str]]: A tuple where the
                first element is a list of required dependencies and the
                second element is a list of optional dependencies
        """
        attrs = struct_to_dict(config.attributes)
        cam = attrs.get(cam_attr)
        if cam is None:
            raise Exception(f"Missing required {cam_attr} attribute.")
        if attrs.get(pattern_attr) is None:
            raise Exception(f"Missing required {pattern_attr} attribute.")
        if attrs.get(square_attr) is None:
            raise Exception(f"Missing required {square_attr} attribute.")

        return [str(cam)], []

    def reconfigure(
        self, config: ComponentConfig, dependencies: Mapping[ResourceName, ResourceBase]
    ):
        """This method allows you to dynamically update your service when it receives a new `config` object.

        Args:
            config (ComponentConfig): The new configuration
            dependencies (Mapping[ResourceName, ResourceBase]): Any dependencies (both required and optional)
        """
        attrs = struct_to_dict(config.attributes)

        camera: str = attrs.get(cam_attr)
        self.camera: Camera = dependencies.get(Camera.get_resource_name(camera))
        
        self.pattern_size = attrs.get(pattern_attr)
        self.square_size = attrs.get(square_attr)

        return super().reconfigure(config, dependencies)
    
    async def get_camera_intrinsics(self) -> tuple:
        """Get camera intrinsic parameters"""
        properties = await self.camera.get_properties()
        intrinsics = properties.intrinsic_parameters
        
        K = np.array([
            [intrinsics.focal_x_px, 0, intrinsics.center_x_px],
            [0, intrinsics.focal_y_px, intrinsics.center_y_px],
            [0, 0, 1]
        ], dtype=np.float32)
        
        # These are values from viam's do command
        dist = np.array([
            0.11473497003316879,    # k1 - radial distortion
            -0.31621694564819336,  # k2 - radial distortion  
            0.00024490756914019585,    # p1 - tangential distortion
            -0.0002616790879983455,    # p2 - tangential distortion
            0.2385278344154358     # k3 - radial distortion
        ], dtype=np.float32)
        
        self.logger.debug(f"Camera intrinsics: K shape={K.shape}, dist shape={dist.shape}")
        self.logger.debug(f"Distortion coefficients: {dist}")
        
        return K, dist

    async def get_poses(
        self,
        body_names: List[str],
        *,
        extra: Optional[Mapping[str, Any]] = None,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Dict[str, PoseInFrame]:
        
        cam_images = await self.camera.get_images()
        for image in cam_images[0]:
            # TODO: Check if we should only receive JPEG images. I feel like we should expand to any image format
            if image.mime_type == CameraMimeType.JPEG:
                viam_image = cam_images[0][0].data
                self.logger.debug("Found image from camera")
        if viam_image is None:
            err = "Could not get latest image from camera"
            self.logger.error(err)
            return err, None
        
        pil_image = viam_to_pil_image(viam_image)
        image = np.array(pil_image)
        
        # Convert to grayscale if needed
        if len(image.shape) == 3:
            image = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        
        K, dist = await self.get_camera_intrinsics()

        found, corners = cv2.findChessboardCorners(
            image,
            self.pattern_size,
            flags=cv2.CALIB_CB_ADAPTIVE_THRESH + cv2.CALIB_CB_NORMALIZE_IMAGE
        )
        if not found:
            err = "Could not find chessboard pattern in image"
            self.logger.error(err)
            return err, None
        self.logger.debug(f"Found chessboard with corners: {corners}")
        
        # Refine corner locations to sub-pixel precision
        criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 30, 0.001)
        corners = cv2.cornerSubPix(image, corners, (11, 11), (-1, -1), criteria)
        
        # Generate 3D object points for the chessboard (Z=0 plane)
        objp = np.zeros((self.pattern_size[1] * self.pattern_size[0], 3), np.float32)
        objp[:, :2] = np.mgrid[0:self.pattern_size[0], 0:self.pattern_size[1]].T.reshape(-1, 2)
        objp *= self.square_size
        
        # Solve PnP to get pose
        success, rvec, tvec = cv2.solvePnP(objp, corners, K, dist)
        if not success:
            print("Could not solve PnP for chessboard")
            return None, None
        self.logger.debug(f"Solved PnP")
        self.logger.debug(f"Rotation vector: {rvec}")
        self.logger.debug(f"Translation vector: {tvec}")
        
        # Convert rotation vector to rotation matrix
        R, _ = cv2.Rodrigues(rvec)

        # TODO: Confirm transposing this matrix is actually needed.
        # I'm not convinced this is a row-vector/column vector transposing problem.
        # I think this might be a we're simply just returning the wrong thing in the go RDK.
        # I think we say we're returning the end of the arm position in base frame, but we might be doing the opposite
        ox, oy, oz, theta = call_go_mat2ov(R.T)
        self.logger.debug(f"Translated roation matrix to orientation vector with values ox={ox}, oy={oy}, oz={oz}, theta={theta}")
        
        # Convert tvec to column vector (3x1)
        t = tvec.reshape(3, 1) * 1000  # Convert to mm

        pose_in_frame = PoseInFrame(
            reference_frame=self.camera.name,
            pose=Pose(
                x=t[0],
                y=t[1],
                z=t[2],
                o_x=ox,
                o_y=oy,
                o_z=oz,
                theta=theta
            )
        )
        
        return "pose", pose_in_frame

    async def do_command(
        self,
        command: Mapping[str, ValueTypes],
        *,
        timeout: Optional[float] = None,
        **kwargs
    ) -> Mapping[str, ValueTypes]:
        self.logger.error("`do_command` is not implemented")
        raise NotImplementedError()

    async def get_geometries(
        self, *, extra: Optional[Dict[str, Any]] = None, timeout: Optional[float] = None
    ) -> Sequence[Geometry]:
        self.logger.error("`get_geometries` is not implemented")
        raise NotImplementedError()

