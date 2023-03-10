# Fundamental of Mobile Robot - AUT.710 - 2023
# Exercise 03 - Problem 02
# Hoang Pham, Nadun Ranasinghe

import rclpy
from rclpy.node import Node
import numpy as np
from math import sin, cos, sqrt, pi
from sensor_msgs.msg import JointState
import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse

# Constants
INTERVAL = 0.1
D = 0.44
Radius = 0.12
ODOM_LIMIT = 383
SENSOR_LIMIT = 127
EPSILON = 0.25
R = np.eye(3) * 0.000025
M = np.matrix('0.001, 0, 0; 0, 0.0002, 0; 0, 0, 0.0002')
L0 = np.matrix('7.5; -4.0')
L1 = np.matrix('-5.0; 8.0')
L2 = np.matrix('-7.0; -6.5')


class Server(Node):
    def __init__(self):
        super().__init__('minimal_subscriber')
        # Temporary variables
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        # self.yaw = -4.8 * pi / 6
        self.P = np.eye(3) * 0.1
        self.Q = np.zeros((3, 3))
        self.A = np.eye(3)

        self.ts1 = 0
        self.ts2 = 0

        # Logged variables
        self.x_predict = np.zeros(ODOM_LIMIT + 1)
        self.y_predict = np.zeros(ODOM_LIMIT + 1)
        self.yaw_predict = np.zeros(ODOM_LIMIT + 1)
        self.P_predict = np.zeros((3, 3, ODOM_LIMIT + 1))
        self.P_predict[:, :, 0] = self.P
        self.yaw_predict[0] = self.yaw

        self.x_update = np.zeros(SENSOR_LIMIT + 1)
        self.y_update = np.zeros(SENSOR_LIMIT + 1)
        self.yaw_update = np.zeros(SENSOR_LIMIT + 1)
        self.P_update = np.zeros((3, 3, SENSOR_LIMIT + 1))

        self.tspan1 = [0]
        self.tspan2 = [0]

        self.wl = np.zeros(ODOM_LIMIT + 1)
        self.wr = np.zeros(ODOM_LIMIT + 1)

        self.dist_hat = np.zeros((3, SENSOR_LIMIT + 1))
        self.dist = np.zeros((3, SENSOR_LIMIT + 1))
        self.dist[:, 0:1] = np.matrix(f'{np.sqrt(L0.T @ L0)}; {np.sqrt(L1.T @ L1)}; {np.sqrt(L2.T @ L2)}')
        self.dist_hat[:, 0:1] = self.dist[:, 0:1]
        self.mahalanobis = np.zeros((3, SENSOR_LIMIT + 1))

        # Counter for indexing
        self.odom_count = 0
        self.sensor_count = 0

        # Subscriber
        self.sensor_subscription = self.create_subscription(JointState, '/landmarks', self.sensor_callback, 40)
        self.odom_subscription = self.create_subscription(JointState, '/joint_states', self.odom_callback, 40)
        self.sensor_subscription  # prevent unused variable warning
        self.odom_subscription

    def canvas(self):
        # Turn on interactive mode
        plt.ion()
        fig, ax = plt.subplots(subplot_kw={'aspect': 'equal'})
        plt.xlim([-20, 20])
        plt.ylim([-20, 20])
        plt.grid(color='grey', linestyle='-', linewidth=0.1)
        plt.title("Trajectories")
        plt.xlabel("X-Axis")
        plt.ylabel("Y-Axis")

        # Landmarks
        plt.plot(L0[0, 0], L0[1, 0], linestyle='None', marker="o", label='Landmark 1')
        plt.plot(L1[0, 0], L1[1, 0], linestyle='None', marker="o", label='Landmark 2')
        plt.plot(L2[0, 0], L2[1, 0], linestyle='None', marker="o", label='Landmark 3')

        # Initialization for animation and text labels
        predicted_coordinates = []
        updated_coordinates = []
        predict, = ax.plot(0, 0, 'bo', markersize=1, label="Predicted position")
        update, = ax.plot(0, 0, 'r--', linewidth=1, label="Updated position")
        ax.legend()
        text0 = plt.text(0.2, 0.1, "Time: 0.0", fontsize=10, horizontalalignment='center', verticalalignment='center',
                         transform=ax.transAxes)
        text1 = plt.text(0.2, 0.2, "Coordinate: 0.0, 0.0", fontsize=10, horizontalalignment='center',
                         verticalalignment='center', transform=ax.transAxes)
        text2 = plt.text(0.2, 0.3, "Predicted Dist: 0.0 , 0.0, 0.0", fontsize=10, horizontalalignment='center',
                         verticalalignment='center', transform=ax.transAxes)
        text3 = plt.text(0.2, 0.4, "Measured Dist: 0.0, 0.0, 0.0", fontsize=10, horizontalalignment='center',
                         verticalalignment='center', transform=ax.transAxes)

        # Iterate through time array to plot the robot position and update state and measurement
        for index in range(0, ODOM_LIMIT):
            # Predicted position
            predicted_coordinates.append((self.x_predict[index], self.y_predict[index]))
            x_predict, y_predict = zip(*predicted_coordinates)
            predict.set_xdata(x_predict)
            predict.set_ydata(y_predict)
            text0.set_text(f"Time: {round(self.tspan1[index], 2)}")
            text1.set_text(f"Coordinate: {round(self.x_predict[index], 2)}, {round(self.y_predict[index], 2)}")

            if index % 3 == 0:
                # Updated position
                i = int(index / 3)
                updated_coordinates.append((self.x_update[i], self.y_update[i]))
                text2.set_text(f"Predicted Dist: {round(self.dist_hat[0, i], 2)}, "
                               f"{round(self.dist_hat[1, i], 2)}, {round(self.dist_hat[2, i], 2)}")
                text3.set_text(f"Measured Dist: {round(self.dist[0, i], 2)}, "
                               f"{round(self.dist[1, i], 2)}, {round(self.dist[2, i], 2)}")

                x_update, y_update = zip(*updated_coordinates)
                update.set_xdata(x_update)
                update.set_ydata(y_update)

                lambda_, v = np.linalg.eig(self.P_update[:, :, i])
                ell = Ellipse(xy=(self.x_update[i], self.y_update[i]),
                              width=lambda_[0] * 2, height=lambda_[1] * 2,
                              angle=np.rad2deg(np.arccos(v[0, 0])))
                ell.set_facecolor('none')
                ell.set_edgecolor('black')
                ax.add_artist(ell)

            # Update the frame ~ making animation
            fig.canvas.draw()
            fig.canvas.flush_events()

            # Stop the interactive mode
            if index == ODOM_LIMIT - 1:
                plt.ioff()
                plt.show()

    def plot(self):
        # Create the time arrays
        tspan1 = np.array(self.tspan1)
        tspan2 = np.array(self.tspan2)

        # Plot the wheels velocity
        fig1 = plt.figure(1)
        plt.plot(tspan1, self.wl, label="Left wheel")
        plt.plot(tspan1, self.wr, label="Right wheel")
        plt.grid(color='gray', linestyle='-', linewidth=0.5)
        plt.title("Wheels velocity")
        plt.xlabel("Time (s)")
        plt.ylabel("Speed (rad/s)")

        # Plot the predicted and updated covariances
        fig2 = plt.figure(2)
        plt.plot(tspan1, self.P_predict[0, 0, :], label="Predicted covariance of x")
        plt.plot(tspan1, self.P_predict[1, 1, :], label="Predicted covariance of y")
        plt.plot(tspan1, self.P_predict[2, 2, :], label="Predicted covariance of psi")
        plt.plot(tspan2, self.P_update[0, 0, :], label="Updated covariance of x")
        plt.plot(tspan2, self.P_update[1, 1, :], label="Updated covariance of y")
        plt.plot(tspan2, self.P_update[2, 2, :], label="Updated covariance of psi")
        plt.grid(color='gray', linestyle='-', linewidth=0.5)
        plt.title("Covariances")
        plt.xlabel("Time (s)")
        plt.ylabel("Value")

        # Plot the predicted and measured distance to landmark
        fig3 = plt.figure(3)
        plt.plot(tspan2, self.dist[0, :], label="Sorted distance 1")
        plt.plot(tspan2, self.dist[1, :], label="Sorted distance 2")
        plt.plot(tspan2, self.dist[2, :], label="Sorted distance 3")
        plt.plot(tspan2, self.dist_hat[0, :], label="Predicted distance LM1")
        plt.plot(tspan2, self.dist_hat[1, :], label="Predicted distance LM2")
        plt.plot(tspan2, self.dist_hat[2, :], label="Predicted distance LM3")
        plt.grid(color='gray', linestyle='-', linewidth=0.5)
        plt.title("Distance to Landmarks")
        plt.xlabel("Time (s)")
        plt.ylabel("Distance")

        fig4, axs4 = plt.subplots(3)
        p_x = np.sqrt(self.P_predict[0, 0, :])
        p_y = np.sqrt(self.P_predict[1, 1, :])
        p_yaw = np.sqrt(self.P_predict[2, 2, :])

        axs4[0].plot(tspan1, self.x_predict, label="X")
        axs4[0].plot(tspan1, self.x_predict + p_x, label="X + Sigma")
        axs4[0].plot(tspan1, self.x_predict - p_x, label="X - Sigma")
        axs4[0].set_title("X versus Time")
        axs4[0].set_xlabel("Time (s)")
        axs4[0].set_ylabel("Value")
        axs4[0].grid(color='gray', linestyle='-', linewidth=0.5)

        axs4[1].plot(tspan1, self.y_predict, label="Y")
        axs4[1].plot(tspan1, self.y_predict + p_y, label="Y + Sigma")
        axs4[1].plot(tspan1, self.y_predict - p_y, label="Y - Sigma")
        axs4[1].set_title("Y versus Time")
        axs4[1].set_xlabel("Time (s)")
        axs4[1].set_ylabel("Value")
        axs4[1].grid(color='gray', linestyle='-', linewidth=0.5)

        axs4[2].plot(tspan1, self.yaw_predict, label="Psi")
        axs4[2].plot(tspan1, self.yaw_predict + p_yaw, label="Psi + Sigma")
        axs4[2].plot(tspan1, self.yaw_predict - p_yaw, label="Psi - Sigma")
        axs4[2].set_title("Psi versus Time")
        axs4[2].set_xlabel("Time (s)")
        axs4[2].set_ylabel("Value")
        axs4[2].grid(color='gray', linestyle='-', linewidth=0.5)

        fig5 = plt.figure(5)
        plt.plot(tspan2, self.mahalanobis[0, :], label="Landmark 1")
        plt.plot(tspan2, self.mahalanobis[1, :], label="Landmark 2")
        plt.plot(tspan2, self.mahalanobis[2, :], label="Landmark 3")
        plt.grid(color='gray', linestyle='-', linewidth=0.5)
        plt.title("Mahalanobis Distance to Landmarks")
        plt.xlabel("Time (s)")
        plt.ylabel("Distance")

        # Finish the plot
        fig1.legend()
        fig2.legend()
        fig3.legend()
        fig4.legend()
        fig5.legend()

        # Show the plot but continue the thread
        plt.show(block=False)

    def odom_callback(self, msg):
        # Increase the counter and process the prediction
        self.odom_count += 1
        # self.get_logger().info('Odom says: #%d "%s"' % (self.odom_count, msg.velocity))

        # Calculate dt and save the timestamp
        ts = msg.header.stamp.sec + msg.header.stamp.nanosec / 1e+9
        if self.odom_count == 1:
            self.tspan1.append(0.1)
        else:
            self.tspan1.append(ts - self.ts1 + self.tspan1[-1])

        self.ts1 = ts

        # Prediction
        self.step_calculation(msg.velocity[1], msg.velocity[0], round(self.tspan1[-1] - self.tspan1[-2], 4))

    def sensor_callback(self, msg):
        # Increase the counter and process the update
        self.sensor_count += 1
        # self.get_logger().info('Sensor says: #%d "%s"' % (self.sensor_count, msg.position))

        # Calculate dt and save the timestamp
        ts = msg.header.stamp.sec + msg.header.stamp.nanosec / 1e+9
        if self.ts2 == 0:
            self.tspan2.append(msg.header.stamp.nanosec / 1e+9)
        else:
            self.tspan2.append(ts - self.ts2 + self.tspan2[-1])
        self.ts2 = ts

        # Update
        self.update(msg.position[0], msg.position[1], msg.position[2])

    def update(self, dist_0, dist_1, dist_2):
        # Extract the last value of P, x, y, psi
        index = self.sensor_count
        P = self.P
        x = self.x
        y = self.y
        yaw = self.yaw

        # Predict the measurement
        dist_hat_0 = sqrt((x - L0[0, 0]) ** 2 + (y - L0[1, 0]) ** 2)
        dist_hat_1 = sqrt((x - L1[0, 0]) ** 2 + (y - L1[1, 0]) ** 2)
        dist_hat_2 = sqrt((x - L2[0, 0]) ** 2 + (y - L2[1, 0]) ** 2)

        # Actual and Predicted Measurement vectors
        z = np.array([dist_0, dist_1, dist_2])
        zh = np.array([dist_hat_0, dist_hat_1, dist_hat_2])

        # H linearization
        H = np.zeros((3, 3))
        H[0, :] = np.matrix([x - L0[0, 0], y - L0[1, 0], 0]) / dist_hat_0
        H[1, :] = np.matrix([x - L1[0, 0], y - L1[1, 0], 0]) / dist_hat_1
        H[2, :] = np.matrix([x - L2[0, 0], y - L2[1, 0], 0]) / dist_hat_2

        # Predicted state vector
        state = np.matrix(f'{x};{y};{yaw}')

        # In case there is duplication
        temp = None

        # Iterate through each actual measurement ith
        for i in range(0, 3):
            Xi = []
            Si = []

            # Iterate through each predicted measurement jth
            for j in range(0, 3):
                vij = z[i] - zh[j]
                Sij = H[j:j + 1, 0:3] @ P @ H[j:j + 1, 0:3].T + R[j, j] # covariance of innovation
                Xij = vij.T * np.linalg.inv(Sij) * vij
                Xi.append(Xij)
                Si.append(Sij)

            # Choose the minimum one
            j = np.argmin(Xi)

            # Update the state and covariances by using the matched measurement
            K = P @ H[j:j + 1, 0:3].T * np.linalg.inv(Si[j])
            P = (np.eye(3) - K @ H[j:j + 1, 0:3]) @ P
            P = 0.5 * (P + P.T)
            state = state + K * (z[i] - zh[j])

            self.mahalanobis[j, index] = Xi[j]

            # Save the actual measurement, save to temp if duplicated
            if self.dist[j, index] == 0.0:
                self.dist[j, index] = z[i]
            else:
                temp = z[i]


            # Fill the duplicated actual measurement that did not have a match
            # Choose the empty one for later plot
            if temp is not None:
                for i in range(0, 3):
                    if self.dist[i, index] == 0.0:
                        self.dist[i, index] = temp
                        break

        # Save to temporary variables and logged variables
        self.x = state[0, 0]
        self.y = state[1, 0]
        self.yaw = state[2, 0]
        self.P = P

        self.x_update[index] = state[0, 0]
        self.y_update[index] = state[1, 0]
        self.yaw_update[index] = state[2, 0]
        self.P_update[:, :, index] = P

        self.dist_hat[0, index] = np.matrix(dist_hat_0)
        self.dist_hat[1, index] = np.matrix(dist_hat_1)
        self.dist_hat[2, index] = np.matrix(dist_hat_2)
        print(f"Total distance diff #{self.sensor_count}:",
              np.sum(np.absolute(self.dist[:, index] - self.dist_hat[:, index])))

    def step_calculation(self, wl, wr, interval=INTERVAL):
        rot_head = interval * Radius * (wr - wl) / (2 * D)
        trans_head = interval * Radius * (wr + wl) / 2

        # Extract the last value of the robot state, A, and P matrix
        index = self.odom_count
        x = self.x
        y = self.y
        yaw = self.yaw
        A = self.A
        P = self.P

        # Log the wheels speed
        self.wl[index] = wl
        self.wr[index] = wr

        # Function f
        x_predict = x + trans_head * cos(yaw + rot_head)
        y_predict = y + trans_head * sin(yaw + rot_head)
        yaw_predict = yaw + rot_head * 2

        # Calculate the predicted positions and save to temporary and logged variables
        self.x_predict[index] = x_predict
        self.y_predict[index] = y_predict
        self.yaw_predict[index] = yaw_predict

        self.x = x_predict
        self.y = y_predict
        self.yaw = yaw_predict

        # Linearization
        L = np.eye(3)
        L[0, :] = np.matrix([cos(yaw + rot_head), -trans_head * sin(yaw + rot_head), 0])
        L[1, :] = np.matrix([sin(yaw + rot_head), trans_head * cos(yaw + rot_head), 0])
        L[2, :] = np.matrix([0, 1, 1])

        A[0, 2] = - trans_head * sin(yaw + rot_head)
        A[1, 2] = trans_head * cos(yaw + rot_head)

        # Calculate new covariances matrix
        P = A @ P @ A.T + L @ M @ L.T
        P = 0.5 * (P + P.T)

        # Save to temporary and logged variables
        self.A = A
        self.P = P
        self.P_predict[:, :, index] = P


        # Plot after the last messages
        if index == ODOM_LIMIT:
            self.plot()
            self.canvas()


def main(args=None):
    rclpy.init(args=args)

    server = Server()

    rclpy.spin(server)

    # Destroy the node explicitly
    # (optional - otherwise it will be done automatically
    # when the garbage collector destroys the node object)
    server.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
