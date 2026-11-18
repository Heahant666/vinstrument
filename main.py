
import cv2

# 웹캠 연결
cap = cv2.VideoCapture(0)

while True:
    ret, frame = cap.read()

    if not ret:
        print("카메라를 불러올 수 없습니다.")
        break

    # 좌우 반전
    frame = cv2.flip(frame, 1)

    # 영상 출력
    cv2.imshow("Virtual Instrument", frame)

    # ESC 키를 누르면 종료
    if cv2.waitKey(1) == 27:
        break

cap.release()
cv2.destroyAllWindows()
